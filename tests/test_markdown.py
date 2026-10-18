"""Markdown CLI contracts, with API requests mocked to avoid network access."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from zyte_cli.cli import app
from zyte_cli.client import ZyteClient
from zyte_cli.output import print_dry_run


runner = CliRunner()
URL = "https://example.com"
MARKDOWN = "# Example\n\nReadable **Markdown**.\n"
PAGE_CONTENT = {
    "headline": "Example",
    "text": "Readable Markdown.",
    "metadata": {"language": "en"},
}


@pytest.fixture
def mock_extract():
    """Capture every payload while returning a representative API response."""
    with patch.object(ZyteClient, "extract", new_callable=AsyncMock) as mocked:
        mocked.return_value = {
            "url": URL,
            "statusCode": 200,
            "markdown": MARKDOWN,
        }
        yield mocked


def invoke_markdown(*args: str):
    return runner.invoke(app, ["--api-key", "test", "extract", "markdown", URL, *args])


def test_markdown_default_payload_and_output(mock_extract):
    result = invoke_markdown()

    assert result.exit_code == 0, result.output
    mock_extract.assert_awaited_once_with({"url": URL, "markdown": True})
    assert json.loads(result.output) == {
        "url": URL,
        "status_code": 200,
        "data": MARKDOWN,
    }


@pytest.mark.parametrize(
    ("source", "mapped"),
    [
        ("auto", None),
        ("http", "httpResponseBody"),
        ("browser", "browserHtml"),
        ("browser-only", "browserHtmlOnly"),
    ],
)
def test_markdown_from_uses_markdown_options(mock_extract, source, mapped):
    result = invoke_markdown("--from", source)

    assert result.exit_code == 0, result.output
    expected = {"url": URL, "markdown": True}
    if mapped is not None:
        expected["markdownOptions"] = {"extractFrom": mapped}
    mock_extract.assert_awaited_once_with(expected)


def test_markdown_scope(mock_extract):
    result = invoke_markdown("--scope", "fullPage")

    assert result.exit_code == 0, result.output
    mock_extract.assert_awaited_once_with({
        "url": URL,
        "markdown": True,
        "markdownOptions": {"scope": "fullPage"},
    })


def test_markdown_auto_with_scope(mock_extract):
    result = invoke_markdown("--from", "auto", "--scope", "fullPage")

    assert result.exit_code == 0, result.output
    mock_extract.assert_awaited_once_with({
        "url": URL,
        "markdown": True,
        "markdownOptions": {"scope": "fullPage"},
    })


def test_markdown_page_content(mock_extract):
    mock_extract.return_value["pageContent"] = PAGE_CONTENT

    result = invoke_markdown("--page-content")

    assert result.exit_code == 0, result.output
    mock_extract.assert_awaited_once_with({
        "url": URL,
        "markdown": True,
        "pageContent": True,
    })
    assert json.loads(result.output) == {
        "url": URL,
        "status_code": 200,
        "data": MARKDOWN,
        "page_content": PAGE_CONTENT,
    }


def test_markdown_page_content_missing_is_omitted(mock_extract):
    result = invoke_markdown("--page-content")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "url": URL,
        "status_code": 200,
        "data": MARKDOWN,
    }


def test_markdown_page_content_null_is_retained(mock_extract):
    mock_extract.return_value["pageContent"] = None

    result = invoke_markdown("--page-content")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "url": URL,
        "status_code": 200,
        "data": MARKDOWN,
        "page_content": None,
    }


def test_markdown_combined_options(mock_extract):
    mock_extract.return_value["pageContent"] = PAGE_CONTENT

    result = invoke_markdown(
        "--from", "browser-only", "--scope", "fullPage", "--page-content",
        "--geolocation", "DE", "--output-format", "json", "--quiet",
    )

    assert result.exit_code == 0, result.output
    mock_extract.assert_awaited_once_with({
        "url": URL,
        "markdown": True,
        "markdownOptions": {"extractFrom": "browserHtmlOnly", "scope": "fullPage"},
        "pageContent": True,
        "geolocation": "DE",
    })
    assert json.loads(result.output)["page_content"] == PAGE_CONTENT


def test_markdown_multiple_urls(mock_extract):
    urls = [URL, "https://example.com/second"]

    async def response(payload):
        return {
            "url": payload["url"],
            "statusCode": 200,
            "markdown": f"# {payload['url']}",
        }

    mock_extract.side_effect = response
    result = invoke_markdown(urls[1], "--from", "http", "--scope", "fullPage", "--quiet")

    assert result.exit_code == 0, result.output
    assert mock_extract.await_count == 2
    payloads = [call.args[0] for call in mock_extract.await_args_list]
    assert sorted(payloads, key=lambda payload: payload["url"]) == [
        {
            "url": url,
            "markdown": True,
            "markdownOptions": {"extractFrom": "httpResponseBody", "scope": "fullPage"},
        }
        for url in urls
    ]
    assert json.loads(result.output) == [
        {"url": url, "status_code": 200, "data": f"# {url}"}
        for url in urls
    ]


def test_markdown_json_file(mock_extract, tmp_path):
    output = tmp_path / "result.json"
    result = invoke_markdown("--output-format", "json", "--output", str(output), "--quiet")

    assert result.exit_code == 0, result.output
    assert result.output == ""
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "url": URL,
        "status_code": 200,
        "data": MARKDOWN,
    }
    mock_extract.assert_awaited_once_with({"url": URL, "markdown": True})


@pytest.mark.parametrize("output_format", ["json", "pretty", "table", "csv"])
def test_markdown_output_formats(mock_extract, output_format):
    # Table/CSV fall back to JSON for a single result object.
    result = invoke_markdown("--output-format", output_format, "--quiet")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["data"] == MARKDOWN
    mock_extract.assert_awaited_once_with({"url": URL, "markdown": True})


def test_markdown_invalid_from_does_not_call_api(mock_extract):
    result = invoke_markdown("--from", "invalid")

    assert result.exit_code == 2
    assert "invalid --from" in result.output
    mock_extract.assert_not_awaited()


@pytest.mark.parametrize(
    ("options", "extra_payload"),
    [
        ([], {}),
        (
            ["--from", "browser", "--scope", "fullPage", "--page-content", "--geolocation", "US"],
            {
                "markdownOptions": {"extractFrom": "browserHtml", "scope": "fullPage"},
                "pageContent": True,
                "geolocation": "US",
            },
        ),
    ],
)
def test_markdown_dry_run_does_not_post(options, extra_payload):
    # Exercise the real client validation/dry-run path, not a mocked extract().
    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post,
        patch("zyte_cli.client.print_dry_run", wraps=print_dry_run) as preview,
    ):
        result = runner.invoke(app, [
            "--api-key", "test", "--dry-run", "extract", "markdown", URL, *options,
        ])

    assert result.exit_code == 0, result.output
    preview.assert_called_once_with({"url": URL, "markdown": True, **extra_payload})
    assert "DRY RUN" in result.output
    post.assert_not_awaited()


def test_extract_page_still_requests_page_content(mock_extract):
    mock_extract.return_value = {"url": URL, "statusCode": 200, "pageContent": PAGE_CONTENT}

    result = runner.invoke(app, ["--api-key", "test", "extract", "page", URL])

    assert result.exit_code == 0, result.output
    mock_extract.assert_awaited_once_with({"url": URL, "pageContent": True})
    assert json.loads(result.output) == {
        "url": URL,
        "status_code": 200,
        "data": PAGE_CONTENT,
    }


def test_client_validation_allows_markdown_with_page_content():
    ZyteClient._validate_payload({"url": URL, "markdown": True, "pageContent": True})
