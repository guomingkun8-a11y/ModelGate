"""A bounded, in-process mock router for the local demonstration."""

from __future__ import annotations

import asyncio
import random
import secrets
import time
from collections import defaultdict, deque

from app.persistence.store import Store, timestamp


class Dispatcher:
    def __init__(self, store: Store):
        self.store = store
        self.active: dict[str, int] = defaultdict(int)
        self.windows: dict[str, deque] = defaultdict(deque)
        self.random = random.SystemRandom()

    async def prepare(self, model: str, prompt: str, key: dict, *,
                      simulate_failure: bool = False, stream: bool = False) -> dict:
        started = time.perf_counter()
        record = {"id": "req_" + secrets.token_hex(8), "created_at": timestamp(),
                  "model": model, "provider": "—", "provider_id": "",
                  "status": "running", "status_code": 0, "latency_ms": 0,
                  "input_tokens": 0, "output_tokens": 0, "is_stream": stream,
                  "attempts": [], "is_demo": True, "error": None}
        self.store.save_request(record)
        run = {"record": record, "started": started, "slot": None, "answer": "",
               "input_tokens": max(1, len(prompt.encode("utf-8")) // 4), "finished": False}
        routes = [r for r in self.store.collection("model_routes") if r["model"] == model and r["enabled"]]
        if not routes:
            self.finish(run, 404, "model_not_found")
            return run
        # ponytail: these counters are atomic only inside this single event loop;
        # the production implementation needs Redis Lua + renewable leases.
        window = self.windows[key["id"]]
        now = time.monotonic()
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= key["rpm_limit"]:
            self.finish(run, 429, "rpm_limit_exceeded")
            return run
        window.append(now)
        self.store.touch_key(key["id"])
        allowed = set(routes[0]["provider_ids"])
        candidates = [p for p in self.store.collection("providers") if p["enabled"] and p["id"] in allowed]
        if not candidates:
            self.finish(run, 503, "no_healthy_upstream")
            return run
        attempts = 0
        while candidates and attempts < 3:
            best = max(p["priority"] for p in candidates)
            group = [p for p in candidates if p["priority"] == best]
            provider = self.random.choices(group, weights=[p["weight"] for p in group], k=1)[0]
            candidates.remove(provider)
            if self.active[provider["id"]] >= provider["concurrency_limit"]:
                continue
            attempts += 1
            self.active[provider["id"]] += 1
            run["slot"] = provider["id"]
            attempt_started = time.perf_counter()
            try:
                await asyncio.sleep(.06 + self.random.random() * .06)
            except BaseException:
                self.finish(run, 499, "client_cancelled")
                raise
            failure = simulate_failure and attempts == 1
            attempt = {"provider_id": provider["id"], "provider": provider["name"],
                       "status_code": 503 if failure else 200,
                       "latency_ms": round((time.perf_counter() - attempt_started) * 1000),
                       "error": "simulated_upstream_failure" if failure else None}
            record["attempts"].append(attempt)
            record["provider_id"], record["provider"] = provider["id"], provider["name"]
            self.store.save_request(record)
            if failure:
                self.release(run)
                continue
            run["answer"] = (
                f"这是来自 {provider['name']} 的模拟回答，不会访问真实模型或产生 API 费用。\n\n"
                f"ModelGate 已将你的请求路由到 {model}，完成虚拟密钥验证、额度检查与调用记录。"
                + ("\n\n首个上游发生了模拟故障，网关已自动切换到当前供应商。" if len(record["attempts"]) > 1 else "")
                + "\n\n你可以在请求日志中查看本次调用的供应商、耗时与每一次尝试。"
            )
            return run
        self.finish(run, 503 if attempts else 429,
                    "upstreams_exhausted" if attempts else "concurrency_limit_exceeded")
        return run

    def release(self, run: dict):
        if run["slot"]:
            self.active[run["slot"]] = max(0, self.active[run["slot"]] - 1)
            run["slot"] = None

    def finish(self, run: dict, code: int = 200, error: str | None = None):
        if run["finished"]:
            return
        run["finished"] = True
        record = run["record"]
        record.update(status="success" if code == 200 else "error", status_code=code,
                      error=error, latency_ms=round((time.perf_counter() - run["started"]) * 1000))
        if code == 200:
            record["input_tokens"] = run["input_tokens"]
            record["output_tokens"] = max(1, len(run["answer"].encode("utf-8")) // 4)
        self.release(run)
        self.store.save_request(record)
