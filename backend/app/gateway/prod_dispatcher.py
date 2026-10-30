"""Production dispatcher: real upstream calls over a PostgreSQL-backed repository.

This is the production counterpart of the demo Dispatcher (app.gateway.dispatcher).
It keeps the same high-level flow — virtual key check, RPM window, route
selection, failover across up to max_attempts providers — but drives real HTTPX
calls and persists to PostgreSQL. Redis-based shared limits and circuit
breaking are introduced in later phases (see docs/ROADMAP.md).
"""

from __future__ import annotations

import random
import secrets
import time
from collections import defaultdict, deque

from app.gateway.upstream import (
    OpenAICompatibleClient,
    extract_content,
    extract_usage,
)
from app.persistence.models import GatewayRequest, UpstreamAttempt
from app.persistence.repository import PostgresRepository, normalize_provider_models


class ProdDispatcher:
    def __init__(self, repository: PostgresRepository, client: OpenAICompatibleClient,
                 max_attempts: int = 3, *, limiter_state: dict | None = None):
        self.repo = repository
        self.client = client
        self.max_attempts = max_attempts
        self.random = random.SystemRandom()
        # In-process RPM / concurrency counters. These are intentionally process-
        # local for now; production shared limits move to Redis Lua + leases.
        limiter_state = limiter_state if limiter_state is not None else {}
        self.windows: dict[str, deque] = limiter_state.setdefault("windows", defaultdict(deque))
        self.active: dict[str, int] = limiter_state.setdefault("active", defaultdict(int))

    async def handle(
        self,
        model: str,
        messages: list[dict],
        key: dict,
        *,
        stream: bool = False,
    ) -> dict:
        """Run one gateway request. Returns a result dict with `record` and
        either `content` (non-stream) or the raw upstream payload for streaming.
        """
        started = time.perf_counter()
        record = GatewayRequest(
            id="req_" + secrets.token_hex(8),
            owner_id=key.get("owner_id"),
            key_id=key.get("id"),
            model=model,
            status="running",
            is_stream=stream,
        )
        self.repo.session.add(record)
        await self.repo.session.flush()

        # --- virtual key RPM (in-process) ---
        window = self.windows[key["id"]]
        now = time.monotonic()
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= key["rpm_limit"]:
            record.status = "error"
            record.status_code = 429
            record.error = "rpm_limit_exceeded"
            record.latency_ms = round((time.perf_counter() - started) * 1000)
            await self.repo.session.commit()
            return {"record": self._to_dict(record), "content": None, "error": "rpm_limit_exceeded"}
        window.append(now)
        await self.repo.touch_key(key["id"])

        # --- route selection ---
        routes = [r for r in await self.repo.list_routes(None)
                  if r["model"] == model and r["enabled"]]
        if not routes:
            record.status = "error"
            record.status_code = 404
            record.error = "model_not_found"
            record.latency_ms = round((time.perf_counter() - started) * 1000)
            await self.repo.session.commit()
            return {"record": self._to_dict(record), "content": None, "error": "model_not_found"}

        allowed = set(routes[0]["provider_ids"])
        providers = [p for p in await self.repo.list_providers(None)
                     if p["enabled"] and p["id"] in allowed]
        if not providers:
            record.status = "error"
            record.status_code = 503
            record.error = "no_healthy_upstream"
            record.latency_ms = round((time.perf_counter() - started) * 1000)
            await self.repo.session.commit()
            return {"record": self._to_dict(record), "content": None, "error": "no_healthy_upstream"}

        # --- failover loop ---
        attempts = 0
        candidates = list(providers)
        while candidates and attempts < self.max_attempts:
            best = max(p["priority"] for p in candidates)
            group = [p for p in candidates if p["priority"] == best]
            provider = self.random.choices(group, weights=[p["weight"] for p in group], k=1)[0]
            candidates.remove(provider)
            mapping = next((item for item in normalize_provider_models(provider["models"])
                            if item["public_model"] == model), None)
            if mapping is None:
                continue
            if self.active[provider["id"]] >= provider["concurrency_limit"]:
                continue
            attempts += 1
            self.active[provider["id"]] += 1
            attempt_started = time.perf_counter()
            try:
                api_key = await self.repo.decrypt_provider_key(provider["id"]) or ""
                status_code, data, error = await self.client.complete(
                    provider["base_url"], api_key, mapping["upstream_model"], messages, stream=stream,
                )
            except Exception:
                status_code, data, error = 0, None, "upstream_request_error"
            finally:
                self.active[provider["id"]] = max(0, self.active[provider["id"]] - 1)

            attempt = UpstreamAttempt(
                request_id=record.id,
                provider_id=provider["id"],
                status_code=status_code or None,
                latency_ms=round((time.perf_counter() - attempt_started) * 1000),
                error=error,
            )
            self.repo.session.add(attempt)

            retryable = error in {"connect_error", "upstream_timeout", "upstream_request_error",
                                  "upstream_rate_limited", "upstream_server_error"}
            if status_code and status_code < 400:
                # success
                input_tokens, output_tokens = extract_usage(data)
                content = extract_content(data)
                record.status = "success"
                record.status_code = status_code
                record.input_tokens = input_tokens
                record.output_tokens = output_tokens
                record.latency_ms = round((time.perf_counter() - started) * 1000)
                await self.repo.session.commit()
                return {"record": self._to_dict(record), "content": content,
                        "stream_payload": data if stream else None, "error": None}
            if not retryable:
                # non-retryable upstream error (4xx except 429): stop, no failover
                record.status = "error"
                record.status_code = status_code or 502
                record.error = error or "upstream_client_error"
                record.latency_ms = round((time.perf_counter() - started) * 1000)
                await self.repo.session.commit()
                return {"record": self._to_dict(record), "content": None,
                        "error": error or "upstream_client_error"}

        # exhausted
        record.status = "error"
        record.status_code = 503 if attempts else 429
        record.error = "upstreams_exhausted" if attempts else "concurrency_limit_exceeded"
        record.latency_ms = round((time.perf_counter() - started) * 1000)
        await self.repo.session.commit()
        return {"record": self._to_dict(record), "content": None,
                "error": record.error}

    @staticmethod
    def _to_dict(record: GatewayRequest) -> dict:
        return {
            "id": record.id,
            "model": record.model,
            "status": record.status,
            "status_code": record.status_code,
            "error": record.error,
            "latency_ms": record.latency_ms,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "is_stream": record.is_stream,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "attempts": [],
        }
