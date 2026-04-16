"""render command — browser HTML mode."""

from __future__ import annotations

import asyncio
from typing import Any

from zyte_cli.client import ZyteClient
from zyte_cli.config import ZyteSettings


async def run_render(
    settings: ZyteSettings,
    url: str,
    action_list: list | None = None,
    include_iframes: bool = False,
    javascript: bool | None = None,
    referer: str | None = None,
    geolocation: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"url": url, "browserHtml": True}
    if action_list:
        payload["actions"] = action_list
    if include_iframes:
        payload["includeIframes"] = True
    if javascript is not None:
        payload["javascript"] = javascript
    if referer:
        payload["requestHeaders"] = {"referer": referer}
    if geolocation:
        payload["geolocation"] = geolocation

    async with ZyteClient(settings) as client:
        raw = await client.extract(payload)
        return {
            "url": raw.get("url", url),
            "status_code": raw.get("statusCode"),
            "browser_html": raw.get("browserHtml"),
            "actions": raw.get("actions"),
            "response_headers": raw.get("httpResponseHeaders"),
        }
