"""Small, persistent demo store. No prompts or API key plaintext are stored."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import random
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime | None = None) -> str:
    return (value or utcnow()).isoformat().replace("+00:00", "Z")


def hash_key(key: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    return salt + ":" + hashlib.sha256((salt + key).encode()).hexdigest()


def verify_key(key: str, digest: str) -> bool:
    return hmac.compare_digest(hash_key(key, digest.split(":", 1)[0]), digest)


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # ponytail: one SQLite connection and short locked operations suit a local demo;
        # use PostgreSQL async sessions before running multiple API workers.
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS providers (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS model_routes (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS virtual_keys (
                id TEXT PRIMARY KEY, key_hash TEXT NOT NULL, data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                model TEXT NOT NULL, status TEXT NOT NULL,
                provider_id TEXT NOT NULL, data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS requests_time ON requests(created_at);
            CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        self.seed()
        self.migrate_default_demo_key()
        self.recover_interrupted()

    def close(self):
        self.db.close()

    def collection(self, table: str) -> list[dict]:
        assert table in {"providers", "model_routes", "virtual_keys"}
        with self.lock:
            return [json.loads(row["data"]) for row in self.db.execute(f"SELECT data FROM {table}")]

    def provider(self, provider_id: str) -> dict | None:
        return next((p for p in self.collection("providers") if p["id"] == provider_id), None)

    def set_provider(self, provider: dict):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO providers VALUES (?, ?)",
                            (provider["id"], json.dumps(provider)))

    def create_key(self, name: str, rpm_limit: int, plaintext: str | None = None,
                   key_id: str | None = None) -> tuple[str, dict]:
        plaintext = plaintext or "sk-" + secrets.token_urlsafe(30)
        record = {
            "id": key_id or "key_" + secrets.token_hex(6), "name": name,
            "prefix": plaintext[:12] + "…", "created_at": timestamp(),
            "last_used_at": None, "status": "active", "rpm_limit": rpm_limit,
            "total_requests": 0,
        }
        with self.lock, self.db:
            self.db.execute("INSERT INTO virtual_keys VALUES (?, ?, ?)",
                            (record["id"], hash_key(plaintext), json.dumps(record)))
        return plaintext, record

    def migrate_default_demo_key(self):
        old_key, new_key = "mg-demo-local", "sk-demo-local"
        with self.lock:
            row = self.db.execute(
                "SELECT key_hash, data FROM virtual_keys WHERE id='key_demo'"
            ).fetchone()
            if not row or not verify_key(old_key, row["key_hash"]):
                return
            record = json.loads(row["data"])
            record["prefix"] = new_key[:12] + "…"
            self.db.execute(
                "UPDATE virtual_keys SET key_hash=?, data=? WHERE id='key_demo'",
                (hash_key(new_key), json.dumps(record)),
            )
            self.db.commit()

    def authenticate_key(self, plaintext: str) -> dict | None:
        with self.lock:
            rows = self.db.execute("SELECT key_hash, data FROM virtual_keys").fetchall()
        for row in rows:
            record = json.loads(row["data"])
            if record["status"] == "active" and verify_key(plaintext, row["key_hash"]):
                return record
        return None

    def update_key(self, record: dict):
        with self.lock, self.db:
            self.db.execute("UPDATE virtual_keys SET data=? WHERE id=?",
                            (json.dumps(record), record["id"]))

    def touch_key(self, key_id: str):
        with self.lock:
            record = next((k for k in self.collection("virtual_keys") if k["id"] == key_id), None)
            if record:
                record["last_used_at"] = timestamp()
                record["total_requests"] += 1
                self.update_key(record)

    def save_request(self, record: dict):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO requests VALUES (?, ?, ?, ?, ?, ?)", (
                record["id"], record["created_at"], record["model"], record["status"],
                record["provider_id"], json.dumps(record),
            ))

    def request(self, request_id: str) -> dict | None:
        with self.lock:
            row = self.db.execute("SELECT data FROM requests WHERE id=?", (request_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def requests(self, hours: int = 24, *, q: str = "", status: str = "",
                 model: str = "", provider: str = "") -> list[dict]:
        cutoff = timestamp(utcnow() - timedelta(hours=hours))
        with self.lock:
            rows = self.db.execute(
                "SELECT data FROM requests WHERE created_at>=? ORDER BY created_at DESC",
                (cutoff,),
            ).fetchall()
        records = [json.loads(row["data"]) for row in rows]
        query = q.casefold()
        return [record for record in records
                if (not status or record["status"] == status)
                and (not model or record["model"] == model)
                and (not provider or provider in {record["provider_id"], record["provider"]})
                and (not query or query in " ".join(str(record.get(k, "")) for k in
                     ("id", "model", "provider", "status", "error")).casefold())]

    def provider_stats(self) -> list[dict]:
        records = self.requests(24)
        result = self.collection("providers")
        for provider in result:
            attempts = [attempt for record in records for attempt in record["attempts"]
                        if attempt["provider_id"] == provider["id"]]
            provider["status"] = "healthy" if provider["enabled"] else "disabled"
            provider["latency_ms"] = round(sum(a["latency_ms"] for a in attempts) / len(attempts)) if attempts else 0
            provider["success_rate"] = round(100 * sum(a["status_code"] == 200 for a in attempts) / len(attempts), 1) if attempts else 0
        return result

    def statistics(self, hours: int = 24) -> dict:
        records = self.requests(hours)
        completed = [r for r in records if r["status"] != "running"]
        successful = sum(r["status"] == "success" for r in completed)
        latencies = sorted(r["latency_ms"] for r in completed)
        model_usage = []
        for model in sorted({r["model"] for r in records}):
            subset = [r for r in records if r["model"] == model]
            model_usage.append({"model": model, "requests": len(subset),
                                "tokens": sum(r["input_tokens"] + r["output_tokens"] for r in subset)})
        now = utcnow()
        # 24 buckets keep the chart usable for both one-hour and seven-day windows.
        count = 24
        width = timedelta(hours=hours / count)
        start = now - timedelta(hours=hours)
        series = []
        for index in range(count):
            lower, upper = start + width * index, start + width * (index + 1)
            subset = [r for r in records if timestamp(lower) <= r["created_at"] < timestamp(upper)]
            series.append({"time": timestamp(lower), "label": lower.strftime("%H:%M"),
                           "requests": len(subset), "errors": sum(r["status"] == "error" for r in subset)})
        return {
            "requests": len(records),
            "success_rate": round(successful / len(completed) * 100, 1) if completed else 0,
            "p95_latency_ms": latencies[max(0, math.ceil(len(latencies) * .95) - 1)] if latencies else 0,
            "tokens": sum(r["input_tokens"] + r["output_tokens"] for r in records),
            "series": series, "model_usage": model_usage, "recent_requests": records[:6],
            "providers": self.provider_stats(), "source": "demo",
        }

    def recover_interrupted(self):
        with self.lock:
            rows = self.db.execute("SELECT data FROM requests WHERE status='running'").fetchall()
        for row in rows:
            record = json.loads(row["data"])
            record.update(status="error", status_code=503, error="interrupted_by_restart")
            self.save_request(record)

    def seed(self):
        with self.lock:
            if self.db.execute("SELECT value FROM metadata WHERE name='seeded'").fetchone():
                return
        models = ["gpt-4o-mini", "deepseek-chat", "llama3.2"]
        definitions = [
            ("openai", "OpenAI", "https://api.openai.com/v1", 100, 70),
            ("deepseek", "DeepSeek", "https://api.deepseek.com/v1", 100, 30),
            ("ollama", "Ollama", "http://localhost:11434/v1", 50, 100),
        ]
        for identifier, name, url, priority, weight in definitions:
            self.set_provider({"id": identifier, "name": name, "kind": "模拟 / OpenAI Compatible",
                               "base_url": url, "models": models, "priority": priority,
                               "weight": weight, "enabled": True, "status": "healthy",
                               "latency_ms": 0, "success_rate": 0, "rpm_limit": 120,
                               "concurrency_limit": 8})
        for index, model in enumerate(models):
            record = {"id": f"route_{index + 1}", "model": model,
                      "name": ["通用对话", "推理与代码", "本地轻量模型"][index],
                      "strategy": "priority_weighted", "provider_ids": [p[0] for p in definitions],
                      "enabled": True}
            with self.lock, self.db:
                self.db.execute("INSERT INTO model_routes VALUES (?, ?)", (record["id"], json.dumps(record)))
        self.create_key("本地演示密钥", 60, "sk-demo-local", "key_demo")
        self.create_key("开发环境", 120, key_id="key_development")
        rng = random.Random(42)
        now = utcnow()
        for index in range(96):
            provider_id, provider, _, _, _ = definitions[index % len(definitions)]
            failed = index % 17 == 0
            latency = rng.randint(170, 1250)
            code = 503 if failed else 200
            record = {"id": "req_sample_" + f"{index + 1:04d}",
                      "created_at": timestamp(now - timedelta(minutes=index * 14 + 2)),
                      "model": models[index % len(models)], "provider": provider,
                      "provider_id": provider_id, "status": "error" if failed else "success",
                      "status_code": code, "latency_ms": latency,
                      "input_tokens": rng.randint(64, 900),
                      "output_tokens": 0 if failed else rng.randint(80, 1400),
                      "is_stream": index % 3 == 0,
                      "attempts": [{"provider_id": provider_id, "provider": provider,
                                    "status_code": code, "latency_ms": latency,
                                    "error": "sample_upstream_unavailable" if failed else None}],
                      "is_demo": True, "error": "sample_upstream_unavailable" if failed else None}
            self.save_request(record)
        with self.lock, self.db:
            self.db.execute("INSERT INTO metadata VALUES ('seeded', ?)", (timestamp(),))
