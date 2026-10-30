"""Real OpenAI-compatible upstream adapter.

A single adapter covers OpenAI, DeepSeek and most third-party relay gateways
(one-api / new-api etc.) because they all expose POST /v1/chat/completions with
the same request/response shape. Each provider is configured by its own
base_url and encrypted API key.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpcore
import httpx


@dataclass
class UpstreamResult:
    status_code: int
    content: str | None
    input_tokens: int | None
    output_tokens: int | None
    error: str | None
    latency_ms: int


async def resolve_public_addresses(host: str, port: int) -> list[str]:
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            records = await asyncio.wait_for(
                asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM),
                timeout=5,
            )
        except (OSError, ValueError, asyncio.TimeoutError):
            raise ValueError("无法解析上游域名，请检查 Base URL。") from None
        addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("上游地址必须解析到公网 IP。")
    return addresses


class PublicDNSBackend(httpcore.AnyIOBackend):
    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            addresses = await resolve_public_addresses(host, port)
        except ValueError as error:
            raise httpcore.ConnectError(str(error)) from None
        last_error = None
        for address in addresses:
            try:
                return await super().connect_tcp(
                    address, port, timeout=timeout, local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as error:
                last_error = error
        if last_error:
            raise last_error
        raise httpcore.ConnectError("上游域名没有公网地址。")


class PublicOnlyTransport(httpx.AsyncHTTPTransport):
    def __init__(self, limits: httpx.Limits):
        super().__init__(trust_env=False, limits=limits)
        # httpx exposes no network-backend parameter on AsyncHTTPTransport.
        self._pool._network_backend = PublicDNSBackend()


class OpenAICompatibleClient:
    """Shared HTTPX client with connection pooling across upstreams."""

    def __init__(self, connect_timeout: float = 5.0, request_timeout: float = 30.0):
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=connect_timeout,
                read=request_timeout,
                write=request_timeout,
                pool=connect_timeout,
            ),
            limits=limits,
            transport=PublicOnlyTransport(limits),
            trust_env=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def validate_base_url(self, base_url: str) -> str:
        value = base_url.strip().rstrip("/")
        parsed = urlsplit(value)
        if (parsed.scheme != "https"
                or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment):
            raise ValueError("Base URL 必须是有效的 HTTPS 地址。")
        if parsed.path.rstrip("/").endswith(("/chat/completions", "/models")):
            raise ValueError("请填写 API 根地址（例如包含 /v1），不要填写具体接口路径。")
        try:
            await resolve_public_addresses(parsed.hostname, parsed.port or 443)
        except ValueError as error:
            raise ValueError(str(error)) from None
        return value

    async def list_models(self, base_url: str, api_key: str) -> tuple[int, list[str], str | None]:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            response = await self._client.get(base_url.rstrip("/") + "/models", headers=headers)
        except httpx.ConnectError:
            return 0, [], "connect_error"
        except httpx.TimeoutException:
            return 0, [], "upstream_timeout"
        except httpx.RequestError:
            return 0, [], "upstream_request_error"
        if response.status_code >= 400:
            return response.status_code, [], self._classify_error(response.status_code)
        try:
            data = response.json()
        except ValueError:
            return 502, [], "invalid_upstream_response"
        items = data.get("data") if isinstance(data, dict) else None
        models = [item["id"] for item in items
                  if isinstance(item, dict) and isinstance(item.get("id"), str)] if isinstance(items, list) else []
        if not models:
            return 502, [], "invalid_upstream_response"
        return response.status_code, models, None

    async def complete(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict],
        *,
        stream: bool = False,
        timeout: float | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[int, dict | None, str | None]:
        """Return (status_code, response_json, error_type).

        A non-2xx status is returned as (status, None, error_type) so the
        dispatcher can decide whether to fail over.
        """
        try:
            base_url = await self.validate_base_url(base_url)
        except ValueError:
            return 0, None, "invalid_upstream_url"
        url = base_url + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        # Responses are buffered until the gateway emits its single SSE chunk.
        payload = {"model": model, "messages": messages, "stream": False}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        try:
            request_options = {"timeout": timeout} if timeout is not None else {}
            response = await self._client.post(url, json=payload, headers=headers, **request_options)
        except httpx.ConnectError:
            return 0, None, "connect_error"
        except httpx.TimeoutException:
            return 0, None, "upstream_timeout"
        except httpx.RequestError:
            return 0, None, "upstream_request_error"

        if response.status_code >= 400:
            return response.status_code, None, self._classify_error(response.status_code)

        try:
            data = response.json()
        except ValueError:
            return 502, None, "invalid_upstream_response"
        return response.status_code, data, None

    @staticmethod
    def _classify_error(status_code: int) -> str:
        if status_code == 429:
            return "upstream_rate_limited"
        if 500 <= status_code < 600:
            return "upstream_server_error"
        return "upstream_client_error"


def extract_usage(data: dict | None) -> tuple[int | None, int | None]:
    """Extract prompt/completion tokens from an OpenAI-compatible response.

    Returns (input_tokens, output_tokens); None means the upstream did not
    report usage (never treated as zero).
    """
    if not data:
        return None, None
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None, None
    return usage.get("prompt_tokens"), usage.get("completion_tokens")


def extract_content(data: dict | None) -> str | None:
    if not data:
        return None
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    return None


def now_ms() -> int:
    return int(time.perf_counter() * 1000)
