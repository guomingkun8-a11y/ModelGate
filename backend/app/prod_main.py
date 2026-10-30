"""Production FastAPI entrypoint.

Runs the real gateway: PostgreSQL persistence and real OpenAI-compatible
upstream calls. Administrators configure the shared upstream channels.

    ../.venv/Scripts/python -m uvicorn app.prod_main:app --host 127.0.0.1 --port 8012
"""

from __future__ import annotations

import hmac
import json as _json
import re
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.gateway.prod_dispatcher import ProdDispatcher
from app.gateway.upstream import OpenAICompatibleClient, extract_content, extract_usage
from app.persistence.crypto import KeyCipher
from app.persistence.db import create_engine_and_sessionmaker, upgrade_schema
from app.persistence.models import AuthSession, User
from app.persistence.repository import PostgresRepository
from app.persistence.security import hash_password, hash_session_token, verify_password


class ChatMessage(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    content: str = Field(max_length=16000)


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = Field(min_length=1, max_length=128)
    messages: list[ChatMessage] = Field(min_length=1, max_length=64)
    stream: bool = False


class LoginInput(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    identifier: str | None = Field(default=None, max_length=254)
    email: str | None = Field(default=None, max_length=254)


class RegisterInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=256)


class ProviderModelInput(BaseModel):
    public_model: str = Field(min_length=1, max_length=128)
    upstream_model: str = Field(min_length=1, max_length=128)


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=8, max_length=512)
    api_key: str = Field(default="", max_length=4096)
    models: list[ProviderModelInput] = Field(min_length=1, max_length=100)
    priority: int = Field(default=100, ge=1, le=1000)
    weight: int = Field(default=100, ge=1, le=1000)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    base_url: str | None = Field(default=None, min_length=8, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)
    models: list[ProviderModelInput] | None = Field(default=None, min_length=1, max_length=100)
    priority: int | None = Field(default=None, ge=1, le=1000)
    weight: int | None = Field(default=None, ge=1, le=1000)
    enabled: bool | None = None


class ProviderTestInput(BaseModel):
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)
    provider_id: str | None = Field(default=None, max_length=64)


class PlaygroundMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=16000)


class PlaygroundChatInput(BaseModel):
    provider_id: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    messages: list[PlaygroundMessage] = Field(min_length=1, max_length=64)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=32768)


def validate_model_mappings(models: list[ProviderModelInput]) -> list[dict[str, str]]:
    mappings = [
        {"public_model": model.public_model.strip(), "upstream_model": model.upstream_model.strip()}
        for model in models
    ]
    if any(not item["public_model"] or not item["upstream_model"] for item in mappings):
        raise HTTPException(422, "公开模型名和上游模型 ID 不能为空。")
    aliases = [item["public_model"] for item in mappings]
    if len(set(aliases)) != len(aliases):
        raise HTTPException(422, "公开模型名不能重复。")
    return mappings


class KeyInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    rpm_limit: int = Field(default=60, ge=1, le=1000)


def error_body(message: str, code: str = "request_error") -> dict:
    return {"error": {"message": message, "type": "modelgate_error", "code": code}}


ERROR_MESSAGES = {
    "model_not_found": "未找到可调用的模型路由。",
    "rpm_limit_exceeded": "虚拟密钥已达到每分钟请求限制，请稍后重试。",
    "no_healthy_upstream": "当前模型没有启用的上游。",
    "concurrency_limit_exceeded": "可用上游的并发额度已用尽，请稍后重试。",
    "upstreams_exhausted": "上游调用失败，已耗尽本次可用的切换次数。",
}


def create_prod_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings)
    cipher = KeyCipher(settings.master_key)
    client = OpenAICompatibleClient(
        connect_timeout=settings.connect_timeout_seconds,
        request_timeout=settings.request_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await upgrade_schema(engine, settings)
        yield
        await client.close()
        await engine.dispose()

    application = FastAPI(title="ModelGate", version="0.2.0", lifespan=lifespan)
    application.state.session_factory = session_factory
    application.state.settings = settings
    application.state.client = client
    application.state.cipher = cipher
    application.state.limiter_state = {}
    started_at = time.time()

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173", "http://127.0.0.1:5173",
            "http://localhost:5175", "http://127.0.0.1:5175",
        ],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    bearer = HTTPBearer(auto_error=False)

    async def _session_dep():
        async with session_factory() as session:
            yield session

    async def get_repo(session: AsyncSession = Depends(_session_dep)) -> PostgresRepository:
        return PostgresRepository(session, application.state.cipher)

    async def principal(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
        session: AsyncSession = Depends(_session_dep),
    ) -> dict:
        if not credentials:
            raise HTTPException(401, "登录已失效，请重新登录。")
        token = credentials.credentials
        if hmac.compare_digest(token.encode(), settings.admin_token.encode()):
            return {"id": None, "name": "Admin", "role": "admin", "session_id": None}
        row = (await session.execute(
            select(AuthSession, User)
            .join(User, AuthSession.user_id == User.id)
            .where(AuthSession.token_hash == hash_session_token(token),
                   AuthSession.expires_at > datetime.now(timezone.utc),
                   User.is_active.is_(True))
        )).first()
        if row is None:
            raise HTTPException(401, "登录已失效，请重新登录。")
        auth_session, user = row
        return {"id": user.id, "name": user.name, "email": user.email,
                "role": "user", "session_id": auth_session.id}

    def require_admin(user: dict = Depends(principal)) -> dict:
        if user["role"] != "admin":
            raise HTTPException(403, "此操作仅限管理员。")
        return user

    def owner_id(user: dict) -> str | None:
        return None if user["role"] == "admin" else user["id"]

    def public_provider(provider: dict) -> dict:
        return {
            "id": provider["id"], "name": provider["name"], "kind": provider["kind"],
            "enabled": provider["enabled"], "status": provider["status"],
            "models": [{"public_model": model["public_model"]}
                       for model in provider["models"]],
        }

    async def virtual_key(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
        session: AsyncSession = Depends(_session_dep),
    ):
        if not credentials:
            raise HTTPException(401, "虚拟 API Key 无效或已撤销。")
        repo = PostgresRepository(session, application.state.cipher)
        key = await repo.authenticate_key(credentials.credentials)
        if not key:
            raise HTTPException(401, "虚拟 API Key 无效或已撤销。")
        return key

    @application.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException):
        return JSONResponse(error_body(str(error.detail), f"http_{error.status_code}"),
                            status_code=error.status_code, headers=error.headers)

    # --- health ---

    @application.get("/healthz")
    async def health():
        return {"status": "ok", "mode": settings.mode, "version": "0.2.0"}

    @application.get("/readyz")
    async def ready():
        return {"status": "ready", "storage": "postgresql", "mode": settings.mode}

    # --- authentication ---

    @application.post("/internal/auth/login")
    async def login(body: LoginInput, session: AsyncSession = Depends(_session_dep)):
        identifier = (body.identifier or body.email or "").strip()
        if not identifier:
            raise HTTPException(422, "请输入邮箱或管理员账号。")
        if identifier.casefold() == settings.admin_username.casefold():
            if not hmac.compare_digest(body.password.encode(), settings.admin_password.encode()):
                raise HTTPException(401, "管理员账号或密码错误。")
            return {"token": settings.admin_token, "name": settings.admin_username, "role": "admin"}
        email = identifier.casefold()
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "邮箱或密码错误。")
        token = secrets.token_urlsafe(32)
        session.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token),
                                expires_at=datetime.now(timezone.utc) + timedelta(days=30)))
        await session.commit()
        return {"token": token, "name": user.name, "role": "user"}

    @application.post("/internal/auth/register", status_code=201)
    async def register(body: RegisterInput, session: AsyncSession = Depends(_session_dep)):
        email = body.email.strip().casefold()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise HTTPException(422, "请输入有效的邮箱地址。")
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "称呼不能为空。")
        if (await session.execute(select(User.id).where(User.email == email))).first():
            raise HTTPException(409, "该邮箱已注册，请直接登录。")
        user = User(email=email, name=name, password_hash=hash_password(body.password))
        token = secrets.token_urlsafe(32)
        try:
            session.add(user)
            await session.flush()
            session.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token),
                                    expires_at=datetime.now(timezone.utc) + timedelta(days=30)))
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(409, "该邮箱已注册，请直接登录。") from None
        return {"token": token, "name": user.name, "role": "user"}

    @application.post("/internal/auth/logout")
    async def logout(user: dict = Depends(principal), session: AsyncSession = Depends(_session_dep)):
        if user["session_id"]:
            auth_session = await session.get(AuthSession, user["session_id"])
            if auth_session:
                await session.delete(auth_session)
                await session.commit()
        return {"ok": True}

    # --- metrics / usage ---

    @application.get("/internal/metrics/overview")
    async def overview(hours: int = Query(24, ge=1, le=168),
                       user: dict = Depends(principal), repo: PostgresRepository = Depends(get_repo)):
        stats = await repo.statistics(hours, owner_id(user))
        providers = await repo.list_providers(None)
        if user["role"] != "admin":
            providers = [public_provider(provider) for provider in providers]
        return {**stats, "providers": providers}

    @application.get("/internal/usage")
    async def usage(hours: int = Query(24, ge=1, le=168),
                    user: dict = Depends(principal), repo: PostgresRepository = Depends(get_repo)):
        stats = await repo.statistics(hours, owner_id(user))
        return {
            "total_requests": stats["requests"],
            "input_tokens": stats["input_tokens"], "output_tokens": stats["output_tokens"],
            "total_tokens": stats["tokens"],
            "by_model": stats["model_usage"],
            "series": stats["series"],
        }

    # --- providers ---

    @application.get("/internal/providers")
    async def providers(user: dict = Depends(principal), repo: PostgresRepository = Depends(get_repo)):
        if user["role"] == "admin":
            return await repo.list_providers(include_all=True)
        return [public_provider(provider) for provider in await repo.list_providers(None)]

    @application.post("/internal/providers", status_code=201)
    async def create_provider(body: ProviderCreate, _: dict = Depends(require_admin),
                              repo: PostgresRepository = Depends(get_repo)):
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "供应商名称不能为空。")
        mappings = validate_model_mappings(body.models)
        try:
            base_url = await client.validate_base_url(body.base_url)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        try:
            provider = await repo.create_provider(
                owner_id=None, name=name, base_url=base_url, api_key=body.api_key,
                models=mappings,
                priority=body.priority, weight=body.weight,
            )
            await repo.session.commit()
        except IntegrityError:
            await repo.session.rollback()
            raise HTTPException(409, "供应商配置冲突，请重试。") from None
        return provider

    @application.post("/internal/providers/test")
    async def test_provider(body: ProviderTestInput, _: dict = Depends(require_admin),
                            repo: PostgresRepository = Depends(get_repo)):
        base_url = body.base_url
        api_key = body.api_key or ""
        if body.provider_id:
            existing = await repo.get_provider(body.provider_id, allow_any=True)
            if existing is None:
                raise HTTPException(404, "供应商不存在。")
            base_url = base_url or existing["base_url"]
            if body.api_key is None or body.api_key == "":
                api_key = await repo.decrypt_provider_key(body.provider_id) or ""
        if not base_url:
            raise HTTPException(422, "请填写上游 Base URL。")
        try:
            base_url = await client.validate_base_url(base_url)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        status_code, model_ids, error = await client.list_models(base_url, api_key)
        if error:
            raise HTTPException(502, f"连接测试失败：上游返回 HTTP {status_code}（{error}）。")
        return {"ok": True, "models": model_ids}

    @application.get("/internal/playground/providers")
    async def playground_providers(_: dict = Depends(require_admin),
                                   repo: PostgresRepository = Depends(get_repo)):
        return await repo.list_providers(include_all=True)

    @application.post("/internal/playground/chat")
    async def playground_chat(body: PlaygroundChatInput, _: dict = Depends(require_admin),
                              repo: PostgresRepository = Depends(get_repo)):
        provider = await repo.get_provider(body.provider_id, allow_any=True)
        if provider is None:
            raise HTTPException(404, "上游不存在。")
        if not provider["enabled"]:
            raise HTTPException(422, "该上游已停用。")
        if not any(item["upstream_model"] == body.model for item in provider["models"]):
            raise HTTPException(422, "该模型未配置在所选上游中。")

        api_key = await repo.decrypt_provider_key(body.provider_id) or ""
        started = time.perf_counter()
        status_code, data, error = await client.complete(
            provider["base_url"], api_key, body.model,
            [message.model_dump() for message in body.messages],
            temperature=body.temperature, max_tokens=body.max_tokens,
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        if error:
            details = {
                "connect_error": "无法连接上游，请检查地址和网络。",
                "upstream_timeout": "上游响应超时。",
                "upstream_rate_limited": "上游已限流，请稍后重试。",
                "upstream_client_error": "请检查 API Key、模型 ID 和接口地址。",
                "upstream_server_error": "上游服务发生错误。",
                "invalid_upstream_response": "上游响应格式无效。",
            }
            hint = details.get(error, "上游请求失败。")
            code = f"HTTP {status_code}" if status_code else "网络错误"
            raise HTTPException(502, f"模型测试失败（{code}）：{hint}")

        content = extract_content(data) if isinstance(data, dict) else None
        if not content or not content.strip():
            raise HTTPException(502, "上游没有返回有效的助手文本。")
        input_tokens, output_tokens = extract_usage(data)
        return {"content": content, "latency_ms": latency_ms,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "provider_id": body.provider_id, "model": body.model}

    @application.patch("/internal/providers/{provider_id}")
    async def update_provider(provider_id: str, body: ProviderUpdate,
                              _: dict = Depends(require_admin), repo: PostgresRepository = Depends(get_repo)):
        existing = await repo.get_provider(provider_id, allow_any=True)
        if existing is None:
            raise HTTPException(404, "供应商不存在。")
        try:
            base_url = await client.validate_base_url(body.base_url or existing["base_url"])
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        models = validate_model_mappings(body.models) if body.models is not None else existing["models"]
        name = (body.name if body.name is not None else existing["name"]).strip()
        if not name:
            raise HTTPException(422, "供应商名称不能为空。")
        provider = await repo.update_provider(
            provider_id, owner_id=None, allow_any=True,
            name=name,
            base_url=base_url, api_key=body.api_key,
            models=models,
            priority=body.priority if body.priority is not None else existing["priority"],
            weight=body.weight if body.weight is not None else existing["weight"],
        )
        if provider is None:
            raise HTTPException(404, "供应商不存在。")
        if body.enabled is not None:
            await repo.set_provider_enabled(provider_id, body.enabled,
                                            owner_id=None, allow_any=True)
            provider["enabled"] = body.enabled
            provider["status"] = "unknown" if body.enabled else "disabled"
        await repo.session.commit()
        return provider

    @application.delete("/internal/providers/{provider_id}")
    async def delete_provider(provider_id: str, _: dict = Depends(require_admin),
                              repo: PostgresRepository = Depends(get_repo)):
        deleted = await repo.delete_provider(provider_id, allow_any=True)
        if not deleted:
            raise HTTPException(404, "供应商不存在。")
        await repo.session.commit()
        return {"ok": True}

    @application.post("/internal/providers/{provider_id}/publish")
    async def publish_provider(provider_id: str, _: dict = Depends(require_admin),
                               repo: PostgresRepository = Depends(get_repo)):
        try:
            provider = await repo.publish_provider(provider_id)
            if provider is None:
                raise HTTPException(404, "供应商不存在。")
            await repo.session.commit()
        except IntegrityError:
            await repo.session.rollback()
            raise HTTPException(409, "发布失败，请检查模型路由冲突。") from None
        return provider

    # --- model routes ---

    @application.get("/internal/model-routes")
    async def model_routes(user: dict = Depends(principal), repo: PostgresRepository = Depends(get_repo)):
        routes = await repo.list_routes(None)
        if user["role"] == "admin":
            return routes
        return [{key: route[key] for key in ("id", "model", "name", "provider_ids", "enabled")}
                for route in routes]

    # --- virtual keys ---

    @application.get("/internal/virtual-keys")
    async def keys(user: dict = Depends(principal), repo: PostgresRepository = Depends(get_repo)):
        return await repo.list_keys(owner_id(user))

    @application.post("/internal/virtual-keys", status_code=201)
    async def create_key(body: KeyInput, user: dict = Depends(principal), repo: PostgresRepository = Depends(get_repo)):
        if not body.name.strip():
            raise HTTPException(422, "密钥名称不能为空。")
        plaintext, record = await repo.create_key(body.name.strip(), body.rpm_limit, owner_id(user))
        await repo.session.commit()
        return {"key": plaintext, "record": record}

    @application.delete("/internal/virtual-keys/{key_id}")
    async def revoke_key(key_id: str, user: dict = Depends(principal), repo: PostgresRepository = Depends(get_repo)):
        record = await repo.revoke_key(key_id, owner_id(user))
        if record is None:
            raise HTTPException(404, "虚拟密钥不存在。")
        await repo.session.commit()
        return record

    # --- requests ---

    @application.get("/internal/requests")
    async def requests(
        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
        q: str = Query("", max_length=200), status: str = "", model: str = "",
        provider: str = "", hours: int = Query(24, ge=1, le=168),
        user: dict = Depends(principal),
        repo: PostgresRepository = Depends(get_repo),
    ):
        return await repo.list_requests(hours, page, page_size, q, status, model, provider,
                                        owner_id(user))

    @application.get("/internal/requests/{request_id}")
    async def request_detail(request_id: str, user: dict = Depends(principal),
                             repo: PostgresRepository = Depends(get_repo)):
        record = await repo.get_request(request_id, owner_id(user))
        if record is None:
            raise HTTPException(404, "请求记录不存在。")
        return record

    # --- settings ---

    @application.get("/internal/settings")
    async def settings_info(_: dict = Depends(principal)):
        return {
            "mode": "生产模式", "storage": "PostgreSQL",
            "limiter": "单进程（Redis 共享限流待接入）", "version": "0.2.0",
            "started_at": started_at, "max_attempts": settings.max_attempts,
            "concurrency_limit": 8, "streaming": True,
            "prompt_storage": "关闭", "billing": "上游实际返回的 Token",
        }

    # --- OpenAI-compatible gateway ---

    @application.get("/v1/models")
    async def models(key: dict = Depends(virtual_key), repo: PostgresRepository = Depends(get_repo)):
        routes = await repo.list_routes(None)
        providers = await repo.list_providers(None)
        available_models = {
            model["public_model"]
            for provider in providers if provider["enabled"]
            for model in provider["models"]
        }
        return {"object": "list", "data": [
            {"id": r["model"], "object": "model", "created": 0, "owned_by": "modelgate"}
            for r in routes if r["enabled"] and r["model"] in available_models
        ]}

    @application.post("/v1/chat/completions")
    async def completions(
        body: ChatInput,
        key: dict = Depends(virtual_key),
        repo: PostgresRepository = Depends(get_repo),
    ):
        messages = [{"role": m.role, "content": m.content} for m in body.messages]
        dispatcher = ProdDispatcher(
            repo, application.state.client, settings.max_attempts,
            limiter_state=application.state.limiter_state,
        )
        result = await dispatcher.handle(body.model, messages, key, stream=body.stream)
        record = result["record"]

        if result["error"]:
            status_code = record["status_code"] or 500
            return JSONResponse(
                error_body(ERROR_MESSAGES.get(record["error"], "请求失败。"),
                           record["error"] or "request_error"),
                status_code=status_code, headers={"X-Request-ID": record["id"]},
            )

        if not body.stream:
            return {
                "id": record["id"], "object": "chat.completion", "created": int(time.time()),
                "model": body.model,
                "choices": [{"index": 0, "message": {"role": "assistant",
                                                    "content": result["content"]},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": record["input_tokens"],
                          "completion_tokens": record["output_tokens"],
                          "total_tokens": (record["input_tokens"] or 0) + (record["output_tokens"] or 0)},
            }

        # Streaming: echo the upstream content as a single SSE chunk. Full
        # chunked passthrough lands in the SSE phase (docs/ROADMAP.md stage 3).
        async def stream():
            content = result["content"] or ""
            chunk = {"id": record["id"], "object": "chat.completion.chunk",
                     "created": int(time.time()), "model": body.model,
                     "choices": [{"index": 0, "delta": {"content": content},
                                  "finish_reason": "stop"}]}
            yield "data: " + _json.dumps(chunk, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    return application


app = create_prod_app()
