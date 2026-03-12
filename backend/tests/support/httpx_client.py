from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx


@asynccontextmanager
async def asgi_client(
    app, *, base_url: str = "http://testserver"
) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=base_url) as client:
        yield client


@asynccontextmanager
async def live_client(*, base_url: str, timeout: float = 30.0) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        yield client


def expect_ok(response: httpx.Response) -> dict:
    assert response.headers.get("content-type", "").startswith("application/json"), response.text
    body = response.json()
    assert body.get("ok") is True, response.text
    assert "data" in body, response.text
    return body["data"]


def expect_error(response: httpx.Response) -> dict:
    assert response.headers.get("content-type", "").startswith("application/json"), response.text
    body = response.json()
    assert body.get("ok") is False, response.text
    err = body.get("error")
    assert isinstance(err, dict), response.text
    assert err.get("code"), response.text
    assert err.get("message"), response.text
    return err
