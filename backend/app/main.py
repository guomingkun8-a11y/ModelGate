"""FastAPI app for a self-contained, explicitly simulated ModelGate demo."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from app.gateway.dispatcher import Dispatcher
from app.persistence.store import Store, timestamp


class LoginInput(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class ProviderUpdate(BaseModel):
    enabled: bool


class KeyInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    rpm_limit: int = Field(default=60, ge=1, le=1000)


class DemoInput(BaseModel):
    model: str = Field(default="gpt-4o-mini", min_length=1, max_length=128)
    prompt: str = Field(default="请介绍一下 ModelGate 的故障切换。", min_length=1, max_length=16000)
    simulate_failure: bool = False
    stream: bool = False


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "developer"]
    content: str = Field(max_length=16000)


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = Field(min_length=1, max_length=128)
    messages: list[Message] = Field(min_length=1, max_length=64)
    stream: bool = False


def error_body(message: str, code: str = "request_error") -> dict:
    return {"error": {"message": message, "type": "modelgate_error", "code": code}}


ERROR_MESSAGES = {
    "model_not_found": "未找到可调用的模型路由。",
    "rpm_limit_exceeded": "虚拟密钥已达到每分钟请求限制，请稍后重试。",
    "no_healthy_upstream": "当前模型没有启用的上游，请先启用一个模拟供应商。",
    "concurrency_limit_exceeded": "可用上游的并发额度已用尽，请稍后重试。",
    "upstreams_exhausted": "模拟上游调用失败，已耗尽本次可用的切换次数。",
}


def create_app(db_path: str | Path | None = None) -> FastAPI:
    database_path = db_path or os.getenv(
        "MODEL_GATE_DEMO_DB", str(Path(__file__).resolve().parents[1] / "data" / "modelgate-demo.sqlite3")
    )
    store = Store(database_path)
    dispatcher = Dispatcher(store)
    admin_password = os.getenv("MODEL_GATE_DEMO_PASSWORD", "modelgate-demo")
    admin_token = os.getenv("MODEL_GATE_ADMIN_TOKEN", "mg-admin-local-demo")
    started_at = timestamp()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        store.close()

    application = FastAPI(title="ModelGate Demo", version="0.1.0-demo", lifespan=lifespan)
    application.state.store = store
    application.state.dispatcher = dispatcher
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    bearer = HTTPBearer(auto_error=False)

    def admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if not credentials or not hmac.compare_digest(credentials.credentials.encode(), admin_token.encode()):
            raise HTTPException(401, "管理员登录已失效，请重新进入演示。")

    def virtual_key(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        key = store.authenticate_key(credentials.credentials) if credentials else None
        if not key:
            raise HTTPException(401, "虚拟 API Key 无效或已撤销。")
        return key

    @application.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException):
        return JSONResponse(error_body(str(error.detail), f"http_{error.status_code}"),
                            status_code=error.status_code, headers=error.headers)

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError):
        # Validation errors can include the original credential/prompt input; never echo it.
        fields = [".".join(map(str, item["loc"])) for item in error.errors()]
        return JSONResponse(error_body("参数格式不正确：" + ", ".join(fields), "validation_error"), status_code=422)

    @application.get("/healthz")
    async def health():
        return {"status": "ok", "mode": "demo", "version": "0.1.0-demo"}

    @application.get("/readyz")
    async def ready():
        store.db.execute("SELECT 1").fetchone()
        return {"status": "ready", "storage": "sqlite", "mode": "demo"}

    @application.post("/internal/auth/login")
    async def login(body: LoginInput):
        if not hmac.compare_digest(body.password.encode(), admin_password.encode()):
            raise HTTPException(401, "演示密码不正确。")
        return {"token": admin_token, "name": "Demo Admin"}

    @application.get("/internal/metrics/overview", dependencies=[Depends(admin)])
    async def overview(hours: int = Query(24, ge=1, le=168)):
        return store.statistics(hours)

    @application.get("/internal/providers", dependencies=[Depends(admin)])
    async def providers():
        return store.provider_stats()

    @application.patch("/internal/providers/{provider_id}", dependencies=[Depends(admin)])
    async def update_provider(provider_id: str, body: ProviderUpdate):
        provider = store.provider(provider_id)
        if not provider:
            raise HTTPException(404, "供应商不存在。")
        provider.update(enabled=body.enabled, status="healthy" if body.enabled else "disabled")
        store.set_provider(provider)
        return next(p for p in store.provider_stats() if p["id"] == provider_id)

    @application.get("/internal/model-routes", dependencies=[Depends(admin)])
    async def model_routes():
        return store.collection("model_routes")

    @application.get("/internal/virtual-keys", dependencies=[Depends(admin)])
    async def keys():
        return store.collection("virtual_keys")

    @application.post("/internal/virtual-keys", dependencies=[Depends(admin)], status_code=201)
    async def create_key(body: KeyInput):
        if not body.name.strip():
            raise HTTPException(422, "密钥名称不能为空。")
        plaintext, record = store.create_key(body.name.strip(), body.rpm_limit)
        return {"key": plaintext, "record": record}

    @application.delete("/internal/virtual-keys/{key_id}", dependencies=[Depends(admin)])
    async def revoke_key(key_id: str):
        record = next((key for key in store.collection("virtual_keys") if key["id"] == key_id), None)
        if not record:
            raise HTTPException(404, "虚拟密钥不存在。")
        record["status"] = "revoked"
        store.update_key(record)
        return record

    @application.get("/internal/requests", dependencies=[Depends(admin)])
    async def requests(
        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
        q: str = Query("", max_length=200), status: str = "", model: str = "",
        provider: str = "", hours: int = Query(24, ge=1, le=168),
    ):
        records = store.requests(hours, q=q, status=status, model=model, provider=provider)
        start = (page - 1) * page_size
        return {"items": records[start:start + page_size], "total": len(records),
                "page": page, "page_size": page_size}

    @application.get("/internal/requests/{request_id}", dependencies=[Depends(admin)])
    async def request_detail(request_id: str):
        record = store.request(request_id)
        if not record:
            raise HTTPException(404, "请求记录不存在。")
        return record

    @application.get("/internal/usage", dependencies=[Depends(admin)])
    async def usage(hours: int = Query(24, ge=1, le=168)):
        records = store.requests(hours)
        summary = store.statistics(hours)
        inputs = sum(record["input_tokens"] for record in records)
        outputs = sum(record["output_tokens"] for record in records)
        return {"total_requests": len(records), "input_tokens": inputs,
                "output_tokens": outputs, "total_tokens": inputs + outputs,
                "by_model": summary["model_usage"], "series": summary["series"]}

    @application.get("/internal/settings", dependencies=[Depends(admin)])
    async def settings():
        return {"mode": "本地演示 / 全部模型响应均为模拟", "storage": "SQLite",
                "limiter": "单进程滑动窗口 / 并发计数（非 Redis）", "version": "0.1.0-demo",
                "started_at": started_at, "max_attempts": 3, "concurrency_limit": 8,
                "virtual_key_rpm": 60, "streaming": True,
                "prompt_storage": "关闭", "billing": "模拟 Token，不产生费用"}

    @application.post("/internal/demo/request", dependencies=[Depends(admin)])
    async def demo_request(body: DemoInput):
        # Admin test actions use a dedicated local key so revoking the public demo key
        # does not silently break the administration UI.
        demo_key = {"id": "internal_demo", "rpm_limit": 60}
        run = await dispatcher.prepare(body.model, body.prompt, demo_key,
                                       simulate_failure=body.simulate_failure, stream=body.stream)
        if not run["finished"]:
            if body.stream:
                try:
                    await asyncio.sleep(.15)
                except BaseException:
                    dispatcher.finish(run, 499, "client_cancelled")
                    raise
            dispatcher.finish(run)
        error = run["record"]["error"]
        answer = run["answer"] or ERROR_MESSAGES.get(error, "模拟请求未完成。")
        return {"request": run["record"], "answer": answer}

    @application.get("/v1/models")
    async def models(_: dict = Depends(virtual_key)):
        return {"object": "list", "data": [
            {"id": route["model"], "object": "model", "created": 0, "owned_by": "modelgate-demo"}
            for route in store.collection("model_routes") if route["enabled"]
        ]}

    @application.post("/v1/chat/completions")
    async def completions(body: ChatInput, key: dict = Depends(virtual_key)):
        prompt = "\n".join(message.content for message in body.messages)
        if len(prompt) > 32000:
            raise HTTPException(422, "演示请求的消息总长度不能超过 32000 字符。")
        run = await dispatcher.prepare(body.model, prompt, key, stream=body.stream)
        record = run["record"]
        headers = {"X-Request-ID": record["id"]}
        if run["finished"]:
            if record["status_code"] == 429:
                headers["Retry-After"] = "60"
            return JSONResponse(error_body(ERROR_MESSAGES.get(record["error"], "请求失败。"), record["error"]),
                                status_code=record["status_code"], headers=headers)
        created = int(time.time())
        if not body.stream:
            dispatcher.finish(run)
            return JSONResponse({"id": record["id"], "object": "chat.completion", "created": created,
                                 "model": body.model,
                                 "choices": [{"index": 0, "message": {"role": "assistant", "content": run["answer"]},
                                              "finish_reason": "stop"}],
                                 "usage": {"prompt_tokens": record["input_tokens"],
                                           "completion_tokens": record["output_tokens"],
                                           "total_tokens": record["input_tokens"] + record["output_tokens"]}}, headers=headers)

        def event(delta: dict, finish_reason=None):
            return "data: " + json.dumps({"id": record["id"], "object": "chat.completion.chunk",
                                         "created": created, "model": body.model,
                                         "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]},
                                        ensure_ascii=False) + "\n\n"

        async def stream():
            completed = False
            try:
                yield event({"role": "assistant", "content": ""})
                for start in range(0, len(run["answer"]), 14):
                    await asyncio.sleep(.025)
                    yield event({"content": run["answer"][start:start + 14]})
                yield event({}, "stop")
                completed = True
            finally:
                dispatcher.finish(run, 200 if completed else 499, None if completed else "client_cancelled")
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream", headers={
            **headers, "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
        })

    # One-port preview after `npm run build`. API routes above always take precedence.
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if (dist / "index.html").is_file():
        @application.get("/{path:path}", include_in_schema=False)
        async def frontend(path: str):
            if path.split("/", 1)[0] in {"internal", "v1", "healthz", "readyz"}:
                raise HTTPException(404, "接口不存在。")
            file = (dist / path).resolve()
            if file.is_relative_to(dist.resolve()) and file.is_file():
                return FileResponse(file)
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return application


app = create_app()
