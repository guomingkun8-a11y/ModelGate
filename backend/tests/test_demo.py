import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.main import ChatInput, create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "demo.sqlite3")) as session:
        yield session


@pytest.fixture
def admin(client):
    result = client.post("/internal/auth/login", json={"password": "modelgate-demo"})
    return {"Authorization": "Bearer " + result.json()["token"]}


def test_admin_and_virtual_key_are_separate(client, admin):
    assert client.get("/internal/providers").status_code == 401
    assert client.get("/internal/providers", headers={"Authorization": "Bearer mg-demo-local"}).status_code == 401
    assert client.get("/v1/models", headers=admin).status_code == 401
    assert client.get("/v1/models", headers={"Authorization": "Bearer mg-demo-local"}).status_code == 200
    assert client.post("/internal/auth/login", json={"password": "错误密码"}).status_code == 401


def test_failure_switch_is_logged_and_prompt_is_not_stored(client, admin):
    marker = "private-prompt-not-for-storage"
    result = client.post("/internal/demo/request", headers=admin,
                         json={"model": "gpt-4o-mini", "prompt": marker, "simulate_failure": True})
    assert result.status_code == 200
    record = result.json()["request"]
    assert record["status"] == "success"
    assert [a["status_code"] for a in record["attempts"]] == [503, 200]
    assert len({a["provider_id"] for a in record["attempts"]}) == 2
    detail = client.get("/internal/requests/" + record["id"], headers=admin)
    assert detail.json() == record
    assert marker not in detail.text
    filtered = client.get("/internal/requests", headers=admin, params={"q": record["id"], "status": "success"}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == record["id"]
    assert not any(client.app.state.dispatcher.active.values())


def test_all_providers_disabled_is_recorded(client, admin):
    for provider in client.get("/internal/providers", headers=admin).json():
        assert client.patch("/internal/providers/" + provider["id"], headers=admin, json={"enabled": False}).status_code == 200
    result = client.post("/internal/demo/request", headers=admin, json={"model": "gpt-4o-mini", "prompt": "hello"}).json()
    assert result["request"]["status_code"] == 503
    assert result["request"]["error"] == "no_healthy_upstream"
    assert client.get("/internal/requests/" + result["request"]["id"], headers=admin).status_code == 200


def test_new_key_works_once_revoked_it_fails(client, admin):
    created = client.post("/internal/virtual-keys", headers=admin, json={"name": "测试", "rpm_limit": 1})
    assert created.status_code == 201
    payload = created.json()
    headers = {"Authorization": "Bearer " + payload["key"]}
    assert payload["key"] not in client.get("/internal/virtual-keys", headers=admin).text
    request = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}
    assert client.post("/v1/chat/completions", headers=headers, json=request).status_code == 200
    limited = client.post("/v1/chat/completions", headers=headers, json=request)
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "60"
    assert client.delete("/internal/virtual-keys/" + payload["record"]["id"], headers=admin).status_code == 200
    assert client.get("/v1/models", headers=headers).status_code == 401


def test_sse_is_incremental_and_finishes_with_done(client, admin):
    with client.stream("POST", "/v1/chat/completions", headers={"Authorization": "Bearer mg-demo-local"},
                       json={"model": "gpt-4o-mini", "stream": True,
                             "messages": [{"role": "user", "content": "hello"}]}) as response:
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("text/event-stream")
        request_id = response.headers["X-Request-ID"]
        events = [line[6:] for line in response.iter_lines() if line.startswith("data: ")]
    assert len(events) > 3
    assert events[-1] == "[DONE]"
    assert json.loads(events[0])["choices"][0]["delta"]["role"] == "assistant"
    assert client.get("/internal/requests/" + request_id, headers=admin).json()["status"] == "success"
    assert not any(client.app.state.dispatcher.active.values())


def test_records_and_provider_state_survive_restart(tmp_path):
    path = tmp_path / "persistent.sqlite3"
    with TestClient(create_app(path)) as client:
        token = client.post("/internal/auth/login", json={"password": "modelgate-demo"}).json()["token"]
        headers = {"Authorization": "Bearer " + token}
        request_id = client.post("/internal/demo/request", headers=headers, json={"prompt": "persist"}).json()["request"]["id"]
        client.patch("/internal/providers/openai", headers=headers, json={"enabled": False})
    with TestClient(create_app(path)) as client:
        assert client.get("/internal/requests/" + request_id, headers=headers).status_code == 200
        assert not next(p for p in client.get("/internal/providers", headers=headers).json() if p["id"] == "openai")["enabled"]
        assert client.get("/internal/requests/missing", headers=headers).status_code == 404


def test_statistics_match_log_and_unknown_model(client, admin):
    overview = client.get("/internal/metrics/overview", headers=admin).json()
    requests = client.get("/internal/requests", headers=admin, params={"page_size": 100}).json()
    assert overview["requests"] == requests["total"] == 96
    assert sum(item["requests"] for item in overview["model_usage"]) == 96
    assert sum(item["requests"] for item in overview["series"]) == 96
    unknown = client.post("/v1/chat/completions", headers={"Authorization": "Bearer mg-demo-local"},
                          json={"model": "missing", "messages": [{"role": "user", "content": "hello"}]})
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "model_not_found"
    one_hour = client.get("/internal/metrics/overview", headers=admin, params={"hours": 1}).json()
    assert len(one_hour["series"]) == 24
    assert sum(point["requests"] for point in one_hour["series"]) == one_hour["requests"]


def test_closing_stream_marks_cancelled_and_releases_slot(client):
    async def scenario():
        app = client.app
        endpoint = next(route.endpoint for route in app.routes if route.path == "/v1/chat/completions")
        key = app.state.store.authenticate_key("mg-demo-local")
        response = await endpoint(ChatInput(model="gpt-4o-mini", stream=True,
                                           messages=[{"role": "user", "content": "cancel me"}]), key)
        request_id = response.headers["X-Request-ID"]
        first = await anext(response.body_iterator)
        assert "chat.completion.chunk" in first
        assert sum(app.state.dispatcher.active.values()) == 1
        await response.body_iterator.aclose()
        assert not any(app.state.dispatcher.active.values())
        record = app.state.store.request(request_id)
        assert record["status_code"] == 499
        assert record["error"] == "client_cancelled"

    asyncio.run(scenario())
