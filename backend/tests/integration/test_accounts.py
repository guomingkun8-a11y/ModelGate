from __future__ import annotations

import os
import secrets

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import Settings, get_settings


TEST_DATABASE_URL = os.getenv("MODEL_GATE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="requires an isolated PostgreSQL test database")


def test_registration_login_and_account_data_are_isolated(monkeypatch):
    master_key = Fernet.generate_key().decode()
    monkeypatch.setenv("MASTER_KEY", master_key)
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    get_settings.cache_clear()
    from app.prod_main import create_prod_app

    settings = Settings(_env_file=None, database_url=TEST_DATABASE_URL, master_key=master_key)
    app = create_prod_app(settings)

    async def validate_base_url(value):
        return value.rstrip("/")

    async def list_models(base_url, api_key):
        return 200, ["first-upstream-model"], None

    monkeypatch.setattr(app.state.client, "validate_base_url", validate_base_url)
    monkeypatch.setattr(app.state.client, "list_models", list_models)

    with TestClient(app) as client:
        suffix = secrets.token_hex(6)
        emails = [f"first-{suffix}@example.test", f"second-{suffix}@example.test"]
        provider_ids = []
        public_model = f"customer-chat-{suffix}"
        private_model = f"legacy-private-{suffix}"
        try:
            first = client.post("/internal/auth/register", json={
                "email": emails[0], "name": "First", "password": "password-one",
            })
            second = client.post("/internal/auth/register", json={
                "email": emails[1], "name": "Second", "password": "password-two",
            })
            assert first.status_code == second.status_code == 201
            first_token = first.json()["token"]
            second_token = second.json()["token"]
            first_auth = {"Authorization": f"Bearer {first_token}"}
            second_auth = {"Authorization": f"Bearer {second_token}"}
            account_login = client.post("/internal/auth/login", json={
                "identifier": emails[0].upper(), "password": "password-one",
            })
            assert account_login.status_code == 200
            assert account_login.json()["role"] == "user"
            assert client.post("/internal/auth/login", json={
                "email": emails[0], "password": "wrong-password",
            }).status_code == 401

            admin_login = client.post("/internal/auth/login", json={
                "identifier": settings.admin_username, "password": settings.admin_password,
            })
            assert admin_login.status_code == 200
            assert admin_login.json()["role"] == "admin"
            admin_auth = {"Authorization": f"Bearer {admin_login.json()['token']}"}

            key = client.post("/internal/virtual-keys", headers=first_auth, json={"name": "first key"})
            assert key.status_code == 201
            assert key.json()["key"].startswith("sk-")
            key_id = key.json()["record"]["id"]
            second_key = client.post("/internal/virtual-keys", headers=second_auth, json={"name": "second key"})
            second_key_id = second_key.json()["record"]["id"]
            assert {row["id"] for row in client.get("/internal/virtual-keys", headers=first_auth).json()} == {key_id}
            assert {row["id"] for row in client.get("/internal/virtual-keys", headers=second_auth).json()} == {second_key_id}
            assert client.delete(f"/internal/virtual-keys/{key_id}", headers=second_auth).status_code == 404

            provider_body = {
                "name": "First upstream", "base_url": "https://first.example/v1",
                "api_key": "upstream-secret-one",
                "models": [{"public_model": public_model, "upstream_model": "first-model-v2"}],
            }
            first_provider = client.post("/internal/providers", headers=first_auth, json=provider_body)
            assert first_provider.status_code == 403
            assert client.get("/internal/providers", headers=first_auth).json() == []

            first_provider = client.post("/internal/providers", headers=admin_auth, json=provider_body)
            assert first_provider.status_code == 201
            first_provider_data = first_provider.json()
            first_provider_id = first_provider_data["id"]
            provider_ids.append(first_provider_id)
            assert first_provider_data["owner_id"] is None
            assert first_provider_data["has_api_key"] is True
            assert "upstream-secret-one" not in first_provider.text
            assert "api_key_encrypted" not in first_provider.text

            async def create_legacy_private_provider():
                from sqlalchemy import select
                from app.persistence.models import User
                from app.persistence.repository import PostgresRepository

                async with app.state.session_factory() as session:
                    user = (await session.execute(
                        select(User).where(User.email == emails[0])
                    )).scalar_one()
                    repo = PostgresRepository(session, app.state.cipher)
                    legacy = await repo.create_provider(
                        owner_id=user.id, name="Legacy private upstream",
                        base_url="https://legacy.example/v1", api_key="legacy-secret",
                        models=[{"public_model": private_model,
                                 "upstream_model": "legacy-actual-model"}],
                    )
                    await session.commit()
                    return legacy["id"]

            legacy_provider_id = client.portal.call(create_legacy_private_provider)
            provider_ids.append(legacy_provider_id)

            for auth in (first_auth, second_auth):
                public_providers = client.get("/internal/providers", headers=auth)
                assert public_providers.status_code == 200
                assert public_providers.json() == [{
                    "id": first_provider_id, "name": "First upstream",
                    "kind": "openai_compatible", "enabled": True, "status": "unknown",
                    "models": [{"public_model": public_model}],
                }]
                assert "base_url" not in public_providers.text
                assert "upstream_model" not in public_providers.text
                assert "api_key" not in public_providers.text
                assert client.get("/internal/model-routes", headers=auth).json()[0]["provider_ids"] == [first_provider_id]
            initial_models = client.get("/v1/models", headers={
                "Authorization": f"Bearer {key.json()['key']}"}).json()["data"]
            assert {model["id"] for model in initial_models} == {public_model}
            assert client.post(f"/internal/providers/{legacy_provider_id}/publish",
                               headers=first_auth).status_code == 403

            admin_before_publish = client.get("/internal/providers", headers=admin_auth).json()
            assert {row["id"] for row in admin_before_publish} == {first_provider_id, legacy_provider_id}
            legacy_channel = next(row for row in admin_before_publish if row["id"] == legacy_provider_id)
            assert legacy_channel["owner_id"] is not None
            published = client.post(f"/internal/providers/{legacy_provider_id}/publish", headers=admin_auth)
            assert published.status_code == 200
            assert published.json()["owner_id"] is None
            for auth in (first_auth, second_auth):
                public_providers = client.get("/internal/providers", headers=auth)
                assert {row["id"] for row in public_providers.json()} == {first_provider_id, legacy_provider_id}
                assert private_model in {model["public_model"] for row in public_providers.json()
                                         for model in row["models"]}
                assert "legacy-secret" not in public_providers.text
                assert "legacy-actual-model" not in public_providers.text

            assert client.patch(f"/internal/providers/{first_provider_id}", headers=first_auth,
                                json={"enabled": False}).status_code == 403
            assert client.delete(f"/internal/providers/{first_provider_id}", headers=second_auth).status_code == 403
            assert client.post("/internal/providers/test", headers=first_auth,
                               json={"provider_id": first_provider_id}).status_code == 403
            assert client.get("/internal/playground/providers", headers=first_auth).status_code == 403
            assert client.get("/internal/playground/providers").status_code == 401

            tested = client.post("/internal/providers/test", headers=admin_auth,
                                 json={"provider_id": first_provider_id})
            assert tested.status_code == 200
            assert tested.json()["models"] == ["first-upstream-model"]
            assert {row["id"] for row in client.get(
                "/internal/playground/providers", headers=admin_auth,
            ).json()} == {first_provider_id, legacy_provider_id}

            upstream_calls = []

            async def complete(base_url, api_key, model, messages, **_kwargs):
                upstream_calls.append((base_url, api_key, model, messages))
                return 200, {
                    "choices": [{"message": {"content": "连接成功"}}],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                }, None

            monkeypatch.setattr(app.state.client, "complete", complete)
            chat_body = {"provider_id": first_provider_id, "model": "first-model-v2",
                         "messages": [{"role": "user", "content": "你好"}]}
            assert client.post("/internal/playground/chat", headers=first_auth,
                               json=chat_body).status_code == 403
            chat = client.post("/internal/playground/chat", headers=admin_auth, json=chat_body)
            assert chat.status_code == 200
            assert chat.json()["content"] == "连接成功"
            assert chat.json()["input_tokens"] == 4
            assert upstream_calls == [(
                "https://first.example/v1", "upstream-secret-one", "first-model-v2",
                [{"role": "user", "content": "你好"}],
            )]
            assert "upstream-secret-one" not in chat.text

            async def assert_encrypted_key():
                from sqlalchemy import select
                from app.persistence.models import Provider

                async with app.state.session_factory() as session:
                    row = (await session.execute(select(Provider).where(Provider.id == first_provider_id))).scalar_one()
                    assert row.api_key_encrypted != "upstream-secret-one"
                    assert app.state.cipher.decrypt(row.api_key_encrypted) == "upstream-secret-one"

            client.portal.call(assert_encrypted_key)

            gateway_body = {
                "model": public_model,
                "messages": [{"role": "user", "content": "hello"}],
            }
            first_request = client.post("/v1/chat/completions", headers={
                "Authorization": f"Bearer {key.json()['key']}"}, json=gateway_body)
            second_request = client.post("/v1/chat/completions", headers={
                "Authorization": f"Bearer {second_key.json()['key']}"}, json=gateway_body)
            assert first_request.status_code == second_request.status_code == 200
            assert first_request.json()["choices"][0]["message"]["content"] == "连接成功"
            assert upstream_calls[-2:] == [
                ("https://first.example/v1", "upstream-secret-one", "first-model-v2",
                 [{"role": "user", "content": "hello"}]),
            ] * 2
            for gateway_key in (key.json()["key"], second_key.json()["key"]):
                available_models = client.get("/v1/models", headers={
                    "Authorization": f"Bearer {gateway_key}"}).json()["data"]
                assert {model["id"] for model in available_models} == {public_model, private_model}

            first_logs = client.get("/internal/requests", headers=first_auth).json()
            second_logs = client.get("/internal/requests", headers=second_auth).json()
            assert first_logs["total"] == 1
            assert second_logs["total"] == 1
            listed_request = first_logs["items"][0]
            assert listed_request["provider_id"] == first_provider_id
            assert listed_request["provider"] == "First upstream"
            assert len(listed_request["attempts"]) == 1
            assert listed_request["attempts"][0]["provider"] == "First upstream"
            for search in (listed_request["id"], public_model, "First upstream"):
                matching = client.get("/internal/requests", headers=first_auth,
                                      params={"q": search}).json()
                assert matching["total"] == 1
                assert matching["items"][0]["id"] == listed_request["id"]
            for search in ("no-such-request", second_logs["items"][0]["id"]):
                assert client.get("/internal/requests", headers=first_auth,
                                  params={"q": search}).json()["total"] == 0
            for provider_filter in (first_provider_id, "First upstream"):
                assert client.get("/internal/requests", headers=first_auth,
                                  params={"provider": provider_filter}).json()["total"] == 1
            assert client.get("/internal/requests", headers=first_auth,
                              params={"provider": "no-such-provider"}).json()["total"] == 0
            assert client.get("/internal/requests", headers=first_auth,
                              params={"status": "error"}).json()["total"] == 0
            assert "base_url" not in str(listed_request)
            assert "upstream-secret-one" not in str(listed_request)
            own_detail = client.get(f"/internal/requests/{first_logs['items'][0]['id']}",
                                    headers=first_auth)
            assert own_detail.status_code == 200
            assert own_detail.json()["attempts"][0]["provider_id"] == first_provider_id
            assert own_detail.json()["provider"] == "First upstream"
            assert client.get("/internal/metrics/overview", headers=second_auth).json()["requests"] == 1
            assert client.get(f"/internal/requests/{first_logs['items'][0]['id']}",
                              headers=second_auth).status_code == 404
            usage = client.get("/internal/usage", headers=second_auth).json()
            assert usage["total_requests"] == 1
            assert (usage["input_tokens"], usage["output_tokens"], usage["total_tokens"]) == (4, 2, 6)

            duplicate = client.post("/internal/auth/register", json={
                "email": emails[0].upper(), "name": "Duplicate", "password": "password-three",
            })
            assert duplicate.status_code == 409

            admin_keys = client.get("/internal/virtual-keys", headers=admin_auth).json()
            assert {record["id"] for record in admin_keys} >= {key_id, second_key_id}
            admin_providers = client.get("/internal/providers", headers=admin_auth).json()
            assert {row["id"] for row in admin_providers} == {first_provider_id, legacy_provider_id}
            assert next(row for row in admin_providers if row["id"] == first_provider_id)["models"][0]["upstream_model"] == "first-model-v2"
            assert client.get("/internal/requests", headers=admin_auth).json()["total"] == 2
            admin_overview = client.get("/internal/metrics/overview", headers=admin_auth).json()
            assert admin_overview["recent_requests"][0]["id"] == second_logs["items"][0]["id"]
            assert admin_overview["recent_requests"][0]["provider"] == "First upstream"
            admin_usage = client.get("/internal/usage", headers=admin_auth).json()
            assert (admin_usage["input_tokens"], admin_usage["output_tokens"], admin_usage["total_tokens"]) == (8, 4, 12)
            assert client.delete(f"/internal/virtual-keys/{second_key_id}", headers=admin_auth).status_code == 200
            assert client.post("/internal/auth/login", json={
                "password": settings.admin_password,
            }).status_code == 422

            assert client.post("/internal/auth/logout", headers=first_auth).json() == {"ok": True}
            assert client.get("/internal/virtual-keys", headers=first_auth).status_code == 401
        finally:
            async def cleanup():
                from sqlalchemy import delete, select
                from app.persistence.models import AuthSession, GatewayRequest, ModelRoute, Provider, User, VirtualKey

                async with app.state.session_factory() as session:
                    await session.execute(delete(ModelRoute).where(ModelRoute.model.in_([public_model, private_model])))
                    if provider_ids:
                        await session.execute(delete(Provider).where(Provider.id.in_(provider_ids)))
                    user_ids = (await session.execute(select(User.id).where(User.email.in_(emails)))).scalars().all()
                    if user_ids:
                        await session.execute(delete(GatewayRequest).where(GatewayRequest.owner_id.in_(user_ids)))
                        await session.execute(delete(VirtualKey).where(VirtualKey.owner_id.in_(user_ids)))
                        await session.execute(delete(AuthSession).where(AuthSession.user_id.in_(user_ids)))
                        await session.execute(delete(User).where(User.id.in_(user_ids)))
                        await session.commit()

            client.portal.call(cleanup)
