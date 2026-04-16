"""screenshot command — browser screenshot mode."""

from __future__ import annotations

import asyncio
import base64
from typing import Any

from zyte_cli.client import ZyteClient
from zyte_cli.config import ZyteSettings


async def run_screenshot(
    settings: ZyteSettings,
    url: str,
    action_list: list | None = None,
    image_format: str = "jpeg",
    full_page: bool = False,
    javascript: bool | None = None,
    referer: str | None = None,
    geolocation: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "url": url,
        "screenshot": True,
        "screenshotOptions": {
            "format": image_format,
            "fullPage": full_page,
        },
    }
    if action_list:
        payload["actions"] = action_list
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
            "mime_type": f"image/{image_format}",
            "image_base64": raw.get("screenshot"),
            "actions": raw.get("actions"),
        }
