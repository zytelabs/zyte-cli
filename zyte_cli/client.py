"""Async Zyte API client for the CLI."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx
import typer

from zyte_cli.config import ZyteSettings
from zyte_cli.errors import ZyteAPIError, ZyteRequestValidationError, build_zyte_error, is_retryable_error
from zyte_cli.output import print_verbose, print_dry_run


TEXTUAL_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/javascript",
    "application/xml",
    "application/xhtml+xml",
    "application/ld+json",
)


def _compute_delay(attempt: int, *, rate_limit: bool) -> float:
    if rate_limit:
        return min(30.0 + (attempt * 5.0), 60.0)
    return min(2.0 * attempt, 10.0)


class ZyteClient:
    def __init__(self, settings: ZyteSettings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client or httpx.AsyncClient(timeout=settings.request_timeout_seconds)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> ZyteClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def extract(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_payload(payload)

        if self.settings.dry_run:
            print_dry_run(payload)
            raise typer.Exit(0)

        if self.settings.verbose:
            print_verbose("→ Request payload", payload)

        async def operation() -> dict[str, Any]:
            response = await self._client.post(
                self.settings.base_url,
                auth=(self.settings.api_key, ""),
                json=payload,
                headers={"Accept": "application/json"},
            )
            return await self._handle_response(response)

        result = await self._retry(operation)

        if self.settings.verbose:
            print_verbose("← Response", result)

        return result

    async def _retry(self, operation: Any) -> Any:
        attempt = 0
        while True:
            try:
                return await operation()
            except ZyteAPIError as error:
                if not is_retryable_error(error.status_code, error.error_type):
                    raise

                rate_limit = error.status_code in {429, 503}
                max_retries = (
                    self.settings.rate_limit_max_retries
                    if rate_limit
                    else self.settings.download_error_max_retries
                )
                if attempt >= max_retries:
                    raise

                attempt += 1
                await asyncio.sleep(_compute_delay(attempt, rate_limit=rate_limit))

    async def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        payload: dict[str, Any] | None = None
        if response.content:
            try:
                payload = response.json()
            except json.JSONDecodeError:
                payload = None

        if response.status_code >= 400:
            raise build_zyte_error(response.status_code, payload)

        return payload or {}

    def decode_text_body(self, raw_response: dict[str, Any]) -> str | None:
        body = raw_response.get("httpResponseBody")
        if not body:
            return None

        headers = raw_response.get("httpResponseHeaders") or {}
        content_type = headers.get("content-type") or headers.get("Content-Type") or ""
        if content_type and not self._is_textual_content_type(content_type):
            return None

        try:
            decoded = base64.b64decode(body)
        except (ValueError, TypeError):
            return None

        for encoding in ("utf-8", "latin-1"):
            try:
                return decoded.decode(encoding)
            except UnicodeDecodeError:
                continue
        return None

    @staticmethod
    def _is_textual_content_type(content_type: str) -> bool:
        return any(content_type.startswith(prefix) for prefix in TEXTUAL_CONTENT_TYPES)

    @staticmethod
    def _validate_payload(payload: dict[str, Any]) -> None:
        browser_fields = {"browserHtml", "screenshot", "actions", "includeIframes", "javascript"}
        http_fields = {"httpResponseBody", "httpResponseHeaders", "httpRequestMethod", "httpRequestBody", "requestHeaders"}

        if payload.get("browserHtml") and payload.get("httpResponseBody"):
            raise ZyteRequestValidationError("browserHtml and httpResponseBody cannot be requested together")

        extraction_fields = [
            name
            for name in ("product", "productList", "article", "pageContent", "serp", "jobPosting")
            if payload.get(name)
        ]
        if len(extraction_fields) > 1:
            raise ZyteRequestValidationError("Only one extraction type can be requested at a time")

        if payload.get("browserHtml") or payload.get("screenshot") or payload.get("actions"):
            request_headers = payload.get("requestHeaders") or {}
            invalid_headers = set(request_headers) - {"referer"}
            if invalid_headers:
                raise ZyteRequestValidationError(
                    "Browser requests only support the referer request header"
                )
            if any(field in payload for field in ("httpRequestMethod", "httpRequestBody")):
                raise ZyteRequestValidationError(
                    "Browser requests cannot set custom HTTP method or body"
                )

        if payload.get("httpResponseBody") and any(field in payload for field in browser_fields):
            raise ZyteRequestValidationError(
                "HTTP response body requests cannot include browser-only options"
            )

        if not payload.get("url"):
            raise ZyteRequestValidationError("url is required")
