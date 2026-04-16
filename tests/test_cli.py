"""Tests for Zyte CLI."""

from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from zyte_cli.cli import app
from zyte_cli.client import ZyteClient
from zyte_cli.config import ZyteSettings
from zyte_cli.errors import ZyteAPIError, ZyteRequestValidationError


runner = CliRunner()

FAKE_SETTINGS = ZyteSettings(api_key="test-key")


# --- Helpers ---

def make_client(responses: dict[str, Any]) -> ZyteClient:
    """Return a ZyteClient whose extract() returns responses[payload_key]."""
    client = ZyteClient(FAKE_SETTINGS)

    async def fake_extract(payload: dict) -> dict:
        # Return response keyed by the first extraction field found
        for key in responses:
            if key in payload or payload.get("url"):
                return responses.get("_default", {})
        return {}

    client.extract = fake_extract  # type: ignore
    return client


# --- Config tests ---

def test_get_settings_missing_key(monkeypatch):
    monkeypatch.delenv("ZYTE_API_KEY", raising=False)
    from zyte_cli.config import get_settings
    with pytest.raises(RuntimeError, match="ZYTE_API_KEY is required"):
        get_settings()


def test_get_settings_from_env(monkeypatch):
    monkeypatch.setenv("ZYTE_API_KEY", "env-key")
    from zyte_cli.config import get_settings
    s = get_settings()
    assert s.api_key == "env-key"


def test_get_settings_override():
    from zyte_cli.config import get_settings
    s = get_settings(api_key_override="override-key")
    assert s.api_key == "override-key"


def test_get_scrapy_cloud_settings_missing(monkeypatch):
    monkeypatch.delenv("SCRAPY_CLOUD_API_KEY", raising=False)
    monkeypatch.delenv("SHUB_APIKEY", raising=False)
    from zyte_cli.config import get_scrapy_cloud_settings
    with pytest.raises(RuntimeError, match="SCRAPY_CLOUD_API_KEY"):
        get_scrapy_cloud_settings()


def test_get_scrapy_cloud_settings_from_shub_apikey(monkeypatch):
    monkeypatch.delenv("SCRAPY_CLOUD_API_KEY", raising=False)
    monkeypatch.setenv("SHUB_APIKEY", "shub-key")
    from zyte_cli.config import get_scrapy_cloud_settings
    s = get_scrapy_cloud_settings()
    assert s.api_key == "shub-key"


# --- Error tests ---

def test_zyte_api_error_str():
    e = ZyteAPIError(status_code=429, error_type="/rate-limit", detail="Too many requests")
    assert "429" in str(e)
    assert "/rate-limit" in str(e)


def test_zyte_api_error_exit_code_auth():
    e = ZyteAPIError(status_code=401, error_type=None, detail="Unauthorized")
    assert e.exit_code == 3


def test_zyte_api_error_exit_code_api():
    e = ZyteAPIError(status_code=500, error_type=None, detail="Server error")
    assert e.exit_code == 1


def test_zyte_request_validation_error():
    e = ZyteRequestValidationError(detail="url is required")
    assert str(e) == "url is required"
    assert e.exit_code == 2


# --- Client validation tests ---

def test_client_validate_no_url():
    from zyte_cli.errors import ZyteRequestValidationError
    with pytest.raises(ZyteRequestValidationError, match="url is required"):
        ZyteClient._validate_payload({})


def test_client_validate_browser_and_http():
    with pytest.raises(ZyteRequestValidationError):
        ZyteClient._validate_payload({"url": "https://example.com", "browserHtml": True, "httpResponseBody": True})


def test_client_validate_multiple_extraction_types():
    with pytest.raises(ZyteRequestValidationError, match="Only one extraction"):
        ZyteClient._validate_payload({"url": "https://example.com", "product": True, "article": True})


def test_client_validate_browser_invalid_header():
    with pytest.raises(ZyteRequestValidationError, match="referer"):
        ZyteClient._validate_payload({
            "url": "https://example.com",
            "browserHtml": True,
            "requestHeaders": {"Authorization": "Bearer token"},
        })


def test_client_decode_text_body_utf8():
    client = ZyteClient(FAKE_SETTINGS)
    body = base64.b64encode(b"<html>hello</html>").decode()
    raw = {
        "httpResponseBody": body,
        "httpResponseHeaders": {"content-type": "text/html"},
    }
    assert client.decode_text_body(raw) == "<html>hello</html>"


def test_client_decode_text_body_binary_skipped():
    client = ZyteClient(FAKE_SETTINGS)
    body = base64.b64encode(b"\x89PNG\r\n").decode()
    raw = {
        "httpResponseBody": body,
        "httpResponseHeaders": {"content-type": "image/png"},
    }
    assert client.decode_text_body(raw) is None


# --- Output tests ---

def test_output_json(capsys):
    from zyte_cli.output import OutputFormat, print_result
    print_result({"key": "value"}, fmt=OutputFormat.json)
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["key"] == "value"


def test_output_csv(capsys):
    from zyte_cli.output import OutputFormat, print_result
    data = {"items": [{"a": 1, "b": 2}, {"a": 3, "b": 4}]}
    print_result(data, fmt=OutputFormat.csv)
    out = capsys.readouterr().out
    assert "a,b" in out
    assert "1,2" in out


def test_output_to_file(tmp_path):
    from zyte_cli.output import OutputFormat, print_result
    out_file = str(tmp_path / "result.json")
    print_result({"hello": "world"}, fmt=OutputFormat.json, output_file=out_file, quiet=True)
    with open(out_file) as f:
        parsed = json.load(f)
    assert parsed["hello"] == "world"


# --- CLI smoke tests (no network) ---

def _mock_client_ctx(monkeypatch, extract_response: dict):
    """Monkeypatch ZyteClient.extract to return extract_response."""
    async def fake_extract(self, payload):
        return extract_response

    monkeypatch.setattr(ZyteClient, "extract", fake_extract)


def test_cli_fetch(monkeypatch):
    _mock_client_ctx(monkeypatch, {
        "url": "https://example.com",
        "statusCode": 200,
        "httpResponseBody": base64.b64encode(b"<html>hello</html>").decode(),
        "httpResponseHeaders": {"content-type": "text/html"},
    })
    result = runner.invoke(app, ["--api-key", "test", "fetch", "https://example.com"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status_code"] == 200


def test_cli_render(monkeypatch):
    _mock_client_ctx(monkeypatch, {
        "url": "https://example.com",
        "statusCode": 200,
        "browserHtml": "<html>rendered</html>",
    })
    result = runner.invoke(app, ["--api-key", "test", "render", "https://example.com"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["browser_html"] == "<html>rendered</html>"


def test_cli_extract_product(monkeypatch):
    _mock_client_ctx(monkeypatch, {
        "url": "https://example.com/product",
        "statusCode": 200,
        "product": {"name": "Widget", "price": "9.99"},
    })
    result = runner.invoke(app, ["--api-key", "test", "extract", "product", "https://example.com/product"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["data"]["name"] == "Widget"


def test_cli_extract_invalid_from(monkeypatch):
    _mock_client_ctx(monkeypatch, {})
    result = runner.invoke(app, ["--api-key", "test", "extract", "product", "https://example.com", "--from", "invalid"])
    assert result.exit_code == 2


def test_cli_fetch_mutual_body_exclusion():
    result = runner.invoke(app, [
        "--api-key", "test", "fetch", "https://example.com",
        "--body-text", "hello",
        "--body-base64", "aGVsbG8=",
    ])
    assert result.exit_code == 2


def test_cli_no_api_key(monkeypatch):
    monkeypatch.delenv("ZYTE_API_KEY", raising=False)
    result = runner.invoke(app, ["fetch", "https://example.com"])
    assert result.exit_code == 3


def test_cli_screenshot_saves_image(monkeypatch, tmp_path):
    image_data = b"\x89PNG\r\n\x1a\n"
    _mock_client_ctx(monkeypatch, {
        "url": "https://example.com",
        "statusCode": 200,
        "screenshot": base64.b64encode(image_data).decode(),
    })
    out_file = str(tmp_path / "shot.png")
    result = runner.invoke(app, [
        "--api-key", "test", "screenshot", "https://example.com",
        "--format", "png", "--output", out_file,
    ])
    assert result.exit_code == 0
    with open(out_file, "rb") as f:
        assert f.read() == image_data
