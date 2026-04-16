"""fetch command — HTTP mode."""

from __future__ import annotations

import base64
import asyncio
from typing import Any

from zyte_cli.client import ZyteClient
from zyte_cli.config import ZyteSettings


async def run_fetch(
    settings: ZyteSettings,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body_text: str | None = None,
    body_base64: str | None = None,
    geolocation: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "url": url,
        "httpResponseBody": True,
        "httpRequestMethod": method.upper(),
    }
    if headers:
        payload["requestHeaders"] = headers
    if body_text is not None:
        payload["httpRequestBody"] = base64.b64encode(body_text.encode("utf-8")).decode("ascii")
    elif body_base64 is not None:
        payload["httpRequestBody"] = body_base64
    if geolocation:
        payload["geolocation"] = geolocation

    async with ZyteClient(settings) as client:
        raw = await client.extract(payload)
        headers_out = raw.get("httpResponseHeaders") or {}
        return {
            "url": raw.get("url", url),
            "status_code": raw.get("statusCode"),
            "content_type": headers_out.get("content-type") or headers_out.get("Content-Type"),
            "text": client.decode_text_body(raw),
            "body_base64": raw.get("httpResponseBody"),
            "response_headers": headers_out,
        }
