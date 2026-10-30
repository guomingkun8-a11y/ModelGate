from __future__ import annotations

import asyncio

import pytest

from app.gateway.prod_dispatcher import ProdDispatcher


class Session:
    def __init__(self):
        self.records = []

    def add(self, _record):
        self.records.append(_record)

    async def flush(self):
        pass

    async def commit(self):
        pass


class Repository:
    def __init__(self):
        self.session = Session()

    async def list_routes(self, owner_id):
        self.route_owner = owner_id
        return [{"model": "public-chat", "provider_ids": ["provider-1"], "enabled": True}]

    async def list_providers(self, owner_id):
        self.provider_owner = owner_id
        return [{
            "id": "provider-1", "owner_id": owner_id, "enabled": True,
            "models": [{"public_model": "public-chat", "upstream_model": "actual-model-v3"}],
            "priority": 100, "weight": 100, "concurrency_limit": 4, "base_url": "https://example.test/v1",
        }]

    async def touch_key(self, _key_id):
        pass

    async def decrypt_provider_key(self, _provider_id):
        return "secret"


class Client:
    async def complete(self, _base_url, _api_key, model, _messages, **_kwargs):
        self.model = model
        return 200, {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1},
        }, None


def test_dispatch_uses_shared_routes_and_preserves_request_owner():
    async def run():
        repo = Repository()
        client = Client()
        result = await ProdDispatcher(repo, client).handle(
            "public-chat", [{"role": "user", "content": "hello"}],
            {"id": "key-1", "owner_id": "user-1", "rpm_limit": 30},
        )
        assert result["error"] is None
        assert client.model == "actual-model-v3"
        assert repo.route_owner is repo.provider_owner is None
        assert repo.session.records[0].owner_id == "user-1"

    asyncio.run(run())


def test_rpm_limit_is_shared_across_request_dispatchers():
    async def run():
        limiter_state = {}
        client = Client()
        key = {"id": "key-1", "owner_id": "user-1", "rpm_limit": 1}
        results = []
        for _ in range(2):
            dispatcher = ProdDispatcher(Repository(), client, limiter_state=limiter_state)
            results.append(await dispatcher.handle("public-chat", [], key))
        assert results[0]["error"] is None
        assert results[1]["record"]["status_code"] == 429
        assert results[1]["error"] == "rpm_limit_exceeded"

        other_key = {**key, "id": "key-2", "owner_id": "user-2"}
        result = await ProdDispatcher(Repository(), client, limiter_state=limiter_state).handle(
            "public-chat", [], other_key,
        )
        assert result["error"] is None

    asyncio.run(run())


def test_shared_channel_concurrency_is_released_after_completion():
    async def run():
        limiter_state = {}
        started, release = asyncio.Event(), asyncio.Event()

        class SingleSlotRepository(Repository):
            async def list_providers(self, owner_id):
                providers = await super().list_providers(owner_id)
                providers[0]["concurrency_limit"] = 1
                return providers

        class BlockingClient(Client):
            async def complete(self, *args, **kwargs):
                started.set()
                await release.wait()
                return await super().complete(*args, **kwargs)

        client = BlockingClient()

        async def request(key_id):
            return await ProdDispatcher(
                SingleSlotRepository(), client, limiter_state=limiter_state,
            ).handle("public-chat", [], {"id": key_id, "owner_id": key_id, "rpm_limit": 30})

        first = asyncio.create_task(request("key-1"))
        await started.wait()
        try:
            blocked = await request("key-2")
            assert blocked["record"]["status_code"] == 429
            assert blocked["error"] == "concurrency_limit_exceeded"
        finally:
            release.set()
            completed = await first
        assert completed["error"] is None
        assert (await request("key-3"))["error"] is None
        assert limiter_state["active"]["provider-1"] == 0

    asyncio.run(run())


@pytest.mark.parametrize("upstream_status, upstream_error", [
    (200, None), (401, "upstream_client_error"), (500, "upstream_server_error"),
])
def test_request_latency_measures_elapsed_time(monkeypatch, upstream_status, upstream_error):
    elapsed = [0.0]
    monkeypatch.setattr("app.gateway.prod_dispatcher.time.perf_counter", lambda: elapsed[0])

    class TimedClient(Client):
        async def complete(self, *args, **kwargs):
            elapsed[0] += 0.125
            if upstream_error:
                return upstream_status, None, upstream_error
            return await super().complete(*args, **kwargs)

    result = asyncio.run(ProdDispatcher(Repository(), TimedClient(), max_attempts=1).handle(
        "public-chat", [], {"id": "key-1", "owner_id": "user-1", "rpm_limit": 30},
    ))
    assert result["record"]["latency_ms"] == 125


def test_cancellation_releases_concurrency_without_retrying_another_channel():
    async def run():
        limiter_state = {}
        started = asyncio.Event()

        class TwoChannelRepository(Repository):
            async def list_routes(self, owner_id):
                routes = await super().list_routes(owner_id)
                routes[0]["provider_ids"].append("provider-2")
                return routes

            async def list_providers(self, owner_id):
                providers = await super().list_providers(owner_id)
                return [providers[0], {**providers[0], "id": "provider-2", "priority": 99}]

        class CancellableClient(Client):
            calls = 0

            async def complete(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    started.set()
                    await asyncio.Event().wait()
                return await super().complete(*args, **kwargs)

        client = CancellableClient()
        request = asyncio.create_task(ProdDispatcher(
            TwoChannelRepository(), client, limiter_state=limiter_state,
        ).handle("public-chat", [], {"id": "key-1", "owner_id": "user-1", "rpm_limit": 30}))
        await started.wait()
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        assert client.calls == 1
        assert limiter_state["active"]["provider-1"] == 0

    asyncio.run(run())
