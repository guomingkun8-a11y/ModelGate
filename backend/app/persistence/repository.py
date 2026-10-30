"""Production repository backed by PostgreSQL.

Mirrors the demo Store interface (collection / provider / create_key / etc.)
so the dispatcher and API layer can run against real data with minimal changes.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.crypto import KeyCipher
from app.persistence.models import (
    GatewayRequest,
    ModelRoute,
    Provider,
    UpstreamAttempt,
    VirtualKey,
)
from app.persistence.security import hash_key, verify_key

PROVIDER_FIELDS = (
    "id", "owner_id", "name", "kind", "base_url", "priority", "weight", "enabled",
    "rpm_limit", "concurrency_limit",
)


def normalize_provider_models(raw: str | list | None) -> list[dict[str, str]]:
    try:
        models = json.loads(raw or "[]") if isinstance(raw, str) else (raw or [])
    except (TypeError, ValueError):
        return []
    result = []
    for item in models:
        if isinstance(item, str) and item.strip():
            result.append({"public_model": item.strip(), "upstream_model": item.strip()})
        elif isinstance(item, dict):
            public_model = str(item.get("public_model", "")).strip()
            upstream_model = str(item.get("upstream_model", "")).strip()
            if public_model and upstream_model:
                result.append({"public_model": public_model, "upstream_model": upstream_model})
    return result


class PostgresRepository:
    def __init__(self, session: AsyncSession, cipher: KeyCipher):
        self.session = session
        self.cipher = cipher

    # --- providers ---

    async def list_providers(self, owner_id: str | None = None,
                             *, include_all: bool = False) -> list[dict]:
        query = select(Provider)
        if not include_all:
            query = query.where(Provider.owner_id.is_(None) if owner_id is None
                                else Provider.owner_id == owner_id)
        rows = (await self.session.execute(query.order_by(Provider.created_at.desc()))).scalars().all()
        return [self._provider_dict(row) for row in rows]

    async def get_provider(self, provider_id: str, owner_id: str | None = None,
                           *, allow_any: bool = False) -> dict | None:
        query = select(Provider).where(Provider.id == provider_id)
        if not allow_any:
            query = query.where(Provider.owner_id.is_(None) if owner_id is None
                                else Provider.owner_id == owner_id)
        row = (await self.session.execute(query)).scalar_one_or_none()
        if row is None:
            return None
        return self._provider_dict(row)

    @staticmethod
    def _provider_dict(row: Provider) -> dict:
        item = {field: getattr(row, field) for field in PROVIDER_FIELDS}
        item["models"] = normalize_provider_models(row.models)
        item["has_api_key"] = bool(row.api_key_encrypted)
        item["status"] = "unknown" if row.enabled else "disabled"
        item["latency_ms"] = 0
        item["success_rate"] = 0.0
        return item

    async def upsert_provider(self, item: dict) -> None:
        row = await self.session.get(Provider, item["id"])
        if row is None:
            row = Provider(id=item["id"])
            self.session.add(row)
        for field in PROVIDER_FIELDS:
            if field in item:
                setattr(row, field, item[field])
        if "models" in item:
            row.models = json.dumps(normalize_provider_models(item["models"]))
        if "api_key" in item and item["api_key"]:
            row.api_key_encrypted = self.cipher.encrypt(item["api_key"])
        await self.session.flush()

    async def create_provider(self, *, owner_id: str | None, name: str, base_url: str,
                              api_key: str, models: list[dict],
                              priority: int = 100, weight: int = 100) -> dict:
        row = Provider(
            owner_id=owner_id, name=name, kind="openai_compatible", base_url=base_url,
            api_key_encrypted=self.cipher.encrypt(api_key) if api_key else None,
            priority=priority, weight=weight, enabled=True,
            models=json.dumps(normalize_provider_models(models)),
        )
        self.session.add(row)
        await self.session.flush()
        await self._sync_provider_routes(row)
        await self.session.flush()
        return self._provider_dict(row)

    async def update_provider(self, provider_id: str, *, owner_id: str | None,
                              allow_any: bool = False, name: str, base_url: str,
                              api_key: str | None, models: list[dict],
                              priority: int, weight: int) -> dict | None:
        query = select(Provider).where(Provider.id == provider_id)
        if not allow_any:
            query = query.where(Provider.owner_id.is_(None) if owner_id is None
                                else Provider.owner_id == owner_id)
        row = (await self.session.execute(query)).scalar_one_or_none()
        if row is None:
            return None
        row.name = name
        row.base_url = base_url
        row.priority = priority
        row.weight = weight
        row.models = json.dumps(normalize_provider_models(models))
        if api_key:
            row.api_key_encrypted = self.cipher.encrypt(api_key)
        await self._sync_provider_routes(row)
        await self.session.flush()
        return self._provider_dict(row)

    async def delete_provider(self, provider_id: str, owner_id: str | None = None,
                              *, allow_any: bool = False) -> bool:
        query = select(Provider).where(Provider.id == provider_id)
        if not allow_any:
            query = query.where(Provider.owner_id.is_(None) if owner_id is None
                                else Provider.owner_id == owner_id)
        row = (await self.session.execute(query)).scalar_one_or_none()
        if row is None:
            return False
        routes = await self._routes_for_owner(row.owner_id)
        for route in routes:
            provider_ids = json.loads(route.provider_ids or "[]")
            if row.id not in provider_ids:
                continue
            route.provider_ids = json.dumps([item for item in provider_ids if item != row.id])
            if not json.loads(route.provider_ids):
                await self.session.delete(route)
        await self.session.delete(row)
        await self.session.flush()
        return True

    async def publish_provider(self, provider_id: str) -> dict | None:
        row = await self.session.get(Provider, provider_id)
        if row is None:
            return None
        if row.owner_id is None:
            return self._provider_dict(row)

        previous_owner_id = row.owner_id
        for route in await self._routes_for_owner(previous_owner_id):
            provider_ids = json.loads(route.provider_ids or "[]")
            if row.id not in provider_ids:
                continue
            route.provider_ids = json.dumps([item for item in provider_ids if item != row.id])
            if not json.loads(route.provider_ids):
                await self.session.delete(route)

        row.owner_id = None
        await self._sync_provider_routes(row)
        await self.session.flush()
        return self._provider_dict(row)

    async def _routes_for_owner(self, owner_id: str | None) -> list[ModelRoute]:
        query = select(ModelRoute).where(
            ModelRoute.owner_id.is_(None) if owner_id is None else ModelRoute.owner_id == owner_id
        )
        return list((await self.session.execute(query)).scalars().all())

    async def _sync_provider_routes(self, provider: Provider) -> None:
        routes = await self._routes_for_owner(provider.owner_id)
        by_model = {route.model: route for route in routes}
        mappings = normalize_provider_models(provider.models)
        models = {mapping["public_model"]: mapping["upstream_model"] for mapping in mappings}

        for route in routes:
            provider_ids = json.loads(route.provider_ids or "[]")
            if provider.id not in provider_ids or route.model in models:
                continue
            route.provider_ids = json.dumps([item for item in provider_ids if item != provider.id])
            if not json.loads(route.provider_ids):
                await self.session.delete(route)

        for model in models:
            route = by_model.get(model)
            if route is None:
                route = ModelRoute(
                    owner_id=provider.owner_id, model=model, name=model,
                    strategy="priority_weighted", provider_ids="[]", enabled=True,
                )
                self.session.add(route)
                by_model[model] = route
            provider_ids = json.loads(route.provider_ids or "[]")
            if provider.id not in provider_ids:
                provider_ids.append(provider.id)
                route.provider_ids = json.dumps(provider_ids)

    async def decrypt_provider_key(self, provider_id: str) -> str | None:
        row = await self.session.get(Provider, provider_id)
        if row is None or not row.api_key_encrypted:
            return None
        return self.cipher.decrypt(row.api_key_encrypted)

    # --- model routes ---

    async def list_routes(self, owner_id: str | None = None,
                          *, include_all: bool = False) -> list[dict]:
        query = select(ModelRoute)
        if not include_all:
            query = query.where(ModelRoute.owner_id.is_(None) if owner_id is None
                                else ModelRoute.owner_id == owner_id)
        rows = (await self.session.execute(query.order_by(ModelRoute.model))).scalars().all()
        return [
            {"id": row.id, "model": row.model, "name": row.name,
             "strategy": row.strategy,
             "provider_ids": json.loads(row.provider_ids or "[]"),
             "enabled": row.enabled}
            for row in rows
        ]

    # --- virtual keys ---

    async def list_keys(self, owner_id: str | None = None) -> list[dict]:
        query = select(VirtualKey)
        if owner_id is not None:
            query = query.where(VirtualKey.owner_id == owner_id)
        rows = (await self.session.execute(query)).scalars().all()
        return [
            {"id": row.id, "name": row.name, "prefix": row.prefix,
             "status": row.status, "rpm_limit": row.rpm_limit,
             "total_requests": row.total_requests,
             "created_at": row.created_at.isoformat() if row.created_at else None,
             "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None}
            for row in rows
        ]

    async def authenticate_key(self, plaintext: str) -> dict | None:
        rows = (await self.session.execute(select(VirtualKey))).scalars().all()
        for row in rows:
            if row.status != "active":
                continue
            try:
                if verify_key(plaintext, row.key_hash):
                    return {
                        "id": row.id, "name": row.name, "prefix": row.prefix,
                        "status": row.status, "rpm_limit": row.rpm_limit,
                        "total_requests": row.total_requests,
                        "owner_id": row.owner_id,
                    }
            except Exception:
                continue
        return None

    async def touch_key(self, key_id: str) -> None:
        row = await self.session.get(VirtualKey, key_id)
        if row is not None:
            row.total_requests += 1
            row.last_used_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def create_key(self, name: str, rpm_limit: int, owner_id: str | None = None) -> tuple[str, dict]:
        """Create a virtual key; returns (plaintext, record). The plaintext is
        returned exactly once and never stored."""
        plaintext = "sk-" + secrets.token_urlsafe(30)
        record = VirtualKey(
            owner_id=owner_id,
            name=name,
            key_hash=hash_key(plaintext),
            prefix=plaintext[:12] + "…",
            status="active",
            rpm_limit=rpm_limit,
        )
        self.session.add(record)
        await self.session.flush()
        return plaintext, self._key_dict(record)

    async def revoke_key(self, key_id: str, owner_id: str | None = None) -> dict | None:
        query = select(VirtualKey).where(VirtualKey.id == key_id)
        if owner_id is not None:
            query = query.where(VirtualKey.owner_id == owner_id)
        row = (await self.session.execute(query)).scalar_one_or_none()
        if row is None:
            return None
        row.status = "revoked"
        await self.session.flush()
        return self._key_dict(row)

    async def set_provider_enabled(self, provider_id: str, enabled: bool,
                                   owner_id: str | None = None,
                                   *, allow_any: bool = False) -> dict | None:
        query = select(Provider).where(Provider.id == provider_id)
        if not allow_any:
            query = query.where(Provider.owner_id.is_(None) if owner_id is None
                                else Provider.owner_id == owner_id)
        row = (await self.session.execute(query)).scalar_one_or_none()
        if row is None:
            return None
        row.enabled = enabled
        await self.session.flush()
        return self._provider_dict(row)

    @staticmethod
    def _key_dict(row: VirtualKey) -> dict:
        return {
            "id": row.id, "name": row.name, "prefix": row.prefix,
            "status": row.status, "rpm_limit": row.rpm_limit,
            "total_requests": row.total_requests,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        }

    # --- requests ---

    async def list_requests(
        self,
        hours: int = 24,
        page: int = 1,
        page_size: int = 20,
        q: str = "",
        status: str = "",
        model: str = "",
        provider: str = "",
        owner_id: str | None = None,
    ) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = select(GatewayRequest).where(GatewayRequest.created_at >= cutoff)
        if owner_id is not None:
            query = query.where(GatewayRequest.owner_id == owner_id)
        if status:
            query = query.where(GatewayRequest.status == status)
        if model:
            query = query.where(GatewayRequest.model == model)
        attempt_requests = select(UpstreamAttempt.request_id).outerjoin(
            Provider, UpstreamAttempt.provider_id == Provider.id,
        )
        if q:
            matched_attempts = attempt_requests.where(or_(
                Provider.name.icontains(q, autoescape=True),
                UpstreamAttempt.provider_id.icontains(q, autoescape=True),
            ))
            query = query.where(or_(
                GatewayRequest.id.icontains(q, autoescape=True),
                GatewayRequest.model.icontains(q, autoescape=True),
                GatewayRequest.id.in_(matched_attempts),
            ))
        if provider:
            query = query.where(GatewayRequest.id.in_(attempt_requests.where(or_(
                UpstreamAttempt.provider_id == provider,
                Provider.name.icontains(provider, autoescape=True),
            ))))
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_q)).scalar_one()
        query = query.order_by(GatewayRequest.created_at.desc(), GatewayRequest.id.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(query)).scalars().all()
        items = await self._request_dicts(rows)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_request(self, request_id: str, owner_id: str | None = None) -> dict | None:
        query = select(GatewayRequest).where(GatewayRequest.id == request_id)
        if owner_id is not None:
            query = query.where(GatewayRequest.owner_id == owner_id)
        row = (await self.session.execute(query)).scalar_one_or_none()
        if row is None:
            return None
        return (await self._request_dicts([row]))[0]

    async def _request_dicts(self, rows: list[GatewayRequest]) -> list[dict]:
        if not rows:
            return []
        attempts = (await self.session.execute(
            select(UpstreamAttempt, Provider.name)
            .outerjoin(Provider, UpstreamAttempt.provider_id == Provider.id)
            .where(UpstreamAttempt.request_id.in_([row.id for row in rows]))
            .order_by(UpstreamAttempt.created_at, UpstreamAttempt.id)
        )).all()
        by_request = {row.id: [] for row in rows}
        for attempt, provider_name in attempts:
            by_request[attempt.request_id].append({
                "provider_id": attempt.provider_id, "provider": provider_name or "已删除渠道",
                "status_code": attempt.status_code, "latency_ms": attempt.latency_ms,
                "error": attempt.error,
            })
        result = []
        for row in rows:
            request_attempts = by_request[row.id]
            final_attempt = request_attempts[-1] if request_attempts else {}
            result.append({
                "id": row.id, "created_at": row.created_at.isoformat() if row.created_at else None,
                "model": row.model, "status": row.status, "status_code": row.status_code,
                "error": row.error, "latency_ms": row.latency_ms,
                "input_tokens": row.input_tokens, "output_tokens": row.output_tokens,
                "is_stream": row.is_stream, "provider_id": final_attempt.get("provider_id"),
                "provider": final_attempt.get("provider", ""), "attempts": request_attempts,
            })
        return result

    async def statistics(self, hours: int = 24, owner_id: str | None = None) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = select(GatewayRequest).where(GatewayRequest.created_at >= cutoff)
        if owner_id is not None:
            query = query.where(GatewayRequest.owner_id == owner_id)
        rows = (await self.session.execute(
            query.order_by(GatewayRequest.created_at.desc(), GatewayRequest.id.desc())
        )).scalars().all()
        completed = [r for r in rows if r.status != "running"]
        successful = sum(r.status == "success" for r in completed)
        latencies = sorted(r.latency_ms for r in completed)
        p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0
        input_tokens = sum(r.input_tokens or 0 for r in rows)
        output_tokens = sum(r.output_tokens or 0 for r in rows)

        model_usage = []
        for model in sorted({r.model for r in rows}):
            subset = [r for r in rows if r.model == model]
            model_usage.append({
                "model": model, "requests": len(subset),
                "tokens": sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in subset),
            })

        # 24 buckets for the trend chart.
        series = []
        count = 24
        width = timedelta(hours=hours / count)
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        for index in range(count):
            lower = start + width * index
            upper = lower + width
            subset = [r for r in rows if lower <= r.created_at < upper]
            series.append({
                "time": lower.isoformat(), "label": lower.strftime("%H:%M"),
                "requests": len(subset),
                "errors": sum(r.status == "error" for r in subset),
            })

        return {
            "requests": len(rows),
            "success_rate": round(successful / len(completed) * 100, 1) if completed else 0,
            "p95_latency_ms": p95,
            "tokens": input_tokens + output_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "series": series,
            "model_usage": model_usage,
            "recent_requests": await self._request_dicts(rows[:6]),
        }
