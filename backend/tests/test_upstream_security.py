from __future__ import annotations

import asyncio
import json
import socket

import httpcore
import httpx
import pytest

from app.gateway.upstream import PublicDNSBackend, OpenAICompatibleClient, resolve_public_addresses


def test_dns_resolution_returns_public_ips_and_backend_connects_to_the_ip(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443)),
    ])
    addresses = asyncio.run(resolve_public_addresses("upstream.example", 443))
    assert addresses == ["8.8.8.8", "1.1.1.1"]

    connected = []

    async def connect_tcp(_self, host, port, **_kwargs):
        connected.append((host, port))
        if host == "8.8.8.8":
            raise httpcore.ConnectTimeout("timed out")
        return object()

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect_tcp)
    asyncio.run(PublicDNSBackend().connect_tcp("upstream.example", 443))
    assert connected == [("8.8.8.8", 443), ("1.1.1.1", 443)]


def test_dns_resolution_rejects_a_private_answer_even_if_a_public_ip_is_also_present(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(ValueError, match="公网 IP"):
        asyncio.run(resolve_public_addresses("upstream.example", 443))


def test_upstream_base_url_requires_public_https(monkeypatch):
    async def public_ips(host, _port):
        if host == "127.0.0.1":
            raise ValueError("上游地址必须解析到公网 IP。")
        return ["8.8.8.8"]

    monkeypatch.setattr("app.gateway.upstream.resolve_public_addresses", public_ips)
    client = OpenAICompatibleClient()
    try:
        assert asyncio.run(client.validate_base_url("https://upstream.example/v1")) == "https://upstream.example/v1"
        with pytest.raises(ValueError, match="HTTPS"):
            asyncio.run(client.validate_base_url("http://upstream.example/v1"))
        with pytest.raises(ValueError, match="公网 IP"):
            asyncio.run(client.validate_base_url("https://127.0.0.1/v1"))
    finally:
        asyncio.run(client.close())


@pytest.mark.parametrize("timeout, expected_read", [(None, 30.0), (7.0, 7.0)])
def test_buffered_stream_requests_preserve_or_override_the_configured_timeout(
    monkeypatch, timeout, expected_read,
):
    async def public_ips(_host, _port):
        return ["8.8.8.8"]

    monkeypatch.setattr("app.gateway.upstream.resolve_public_addresses", public_ips)

    async def run():
        client = OpenAICompatibleClient(connect_timeout=5, request_timeout=30)
        configured_timeout = client._client.timeout
        await client._client.aclose()

        def respond(request):
            assert json.loads(request.content)["stream"] is False
            assert request.extensions["timeout"]["read"] == expected_read
            assert request.extensions["timeout"]["connect"] == (5.0 if timeout is None else timeout)
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(respond), timeout=configured_timeout,
        )
        try:
            status, data, error = await client.complete(
                "https://upstream.example/v1", "", "public-chat", [], stream=True,
                timeout=timeout,
            )
            assert status == 200 and error is None
            assert data["choices"][0]["message"]["content"] == "ok"
        finally:
            await client.close()

    asyncio.run(run())
