"""Zyte CLI — root application."""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from zyte_cli.commands import extract, cloud
from zyte_cli.commands.fetch import run_fetch
from zyte_cli.commands.render import run_render
from zyte_cli.commands.screenshot import run_screenshot
from zyte_cli.config import get_settings
from zyte_cli.errors import ZyteAPIError, ZyteRequestValidationError
from zyte_cli.output import OutputFormat, print_error, print_info, print_result

app = typer.Typer(
    name="zyte",
    help="CLI tool for the Zyte API and Scrapy Cloud.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Subcommand groups
app.add_typer(extract.app, name="extract")
app.add_typer(cloud.app, name="cloud")


@app.callback()
def main(
    ctx: typer.Context,
    api_key: Annotated[
        Optional[str],
        typer.Option("--api-key", envvar="ZYTE_API_KEY", help="Zyte API key (overrides ZYTE_API_KEY env var)", show_default=False),
    ] = None,
    cloud_api_key: Annotated[
        Optional[str],
        typer.Option(
            "--cloud-api-key",
            envvar="SCRAPY_CLOUD_API_KEY",
            help="Scrapy Cloud API key (overrides SCRAPY_CLOUD_API_KEY / SHUB_APIKEY)",
            show_default=False,
        ),
    ] = None,
) -> None:
    """[bold]zyte[/bold] — CLI for the Zyte API and Scrapy Cloud.

    Set [bold]ZYTE_API_KEY[/bold] to use Zyte API commands.
    Set [bold]SCRAPY_CLOUD_API_KEY[/bold] (or [bold]SHUB_APIKEY[/bold]) for cloud commands.
    """
    ctx.ensure_object(dict)
    ctx.obj["cloud_api_key"] = cloud_api_key
    ctx.obj["api_key_override"] = api_key

    command_name = ctx.invoked_subcommand
    if command_name and command_name != "cloud":
        try:
            ctx.obj["settings"] = get_settings(api_key_override=api_key)
        except RuntimeError as e:
            print_error(str(e))
            raise typer.Exit(3)
    else:
        ctx.obj["settings"] = None


# ── fetch ─────────────────────────────────────────────────────────────────────

@app.command("fetch")
def cmd_fetch(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="URL to fetch")],
    method: Annotated[str, typer.Option("--method", "-X", help="HTTP method")] = "GET",
    header: Annotated[
        Optional[list[str]],
        typer.Option("--header", "-H", help="Request header as key=value (repeatable)"),
    ] = None,
    body_text: Annotated[Optional[str], typer.Option("--body-text", help="Request body as plain text")] = None,
    body_base64_opt: Annotated[Optional[str], typer.Option("--body-base64", help="Request body as base64")] = None,
    geolocation: Annotated[Optional[str], typer.Option("--geolocation", help="ISO 3166-1 alpha-2 country code")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--output-format", "-f", help="Output format")] = OutputFormat.json,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Write output to file")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress progress output")] = False,
) -> None:
    """Fetch a URL using Zyte HTTP mode (no browser rendering)."""
    if body_text is not None and body_base64_opt is not None:
        print_error("provide only one of --body-text or --body-base64")
        raise typer.Exit(2)

    headers: dict[str, str] = {}
    for h in header or []:
        if "=" not in h:
            print_error(f"invalid header format '{h}', expected key=value")
            raise typer.Exit(2)
        k, v = h.split("=", 1)
        headers[k.strip()] = v.strip()

    result = asyncio.run(run_fetch(
        ctx.obj["settings"], url,
        method=method,
        headers=headers or None,
        body_text=body_text,
        body_base64=body_base64_opt,
        geolocation=geolocation,
    ))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


# ── render ────────────────────────────────────────────────────────────────────

@app.command("render")
def cmd_render(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="URL to render")],
    actions: Annotated[
        Optional[str],
        typer.Option("--actions", help="Path to a JSON file containing browser actions array"),
    ] = None,
    actions_inline: Annotated[
        Optional[str],
        typer.Option("--actions-inline", help="Inline JSON string of browser actions array"),
    ] = None,
    include_iframes: Annotated[bool, typer.Option("--include-iframes", help="Include iframes in output")] = False,
    javascript: Annotated[Optional[bool], typer.Option("--javascript/--no-javascript", help="Enable/disable JavaScript")] = None,
    referer: Annotated[Optional[str], typer.Option("--referer", help="Referer header value")] = None,
    geolocation: Annotated[Optional[str], typer.Option("--geolocation", help="ISO 3166-1 alpha-2 country code")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--output-format", "-f", help="Output format")] = OutputFormat.json,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Write output to file")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress progress output")] = False,
) -> None:
    """Render a page in a real browser and return the HTML."""
    if actions and actions_inline:
        print_error("provide only one of --actions or --actions-inline")
        raise typer.Exit(2)

    action_list: list | None = None
    if actions:
        try:
            with open(actions) as f:
                action_list = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print_error(f"reading actions file: {e}")
            raise typer.Exit(2)
    elif actions_inline:
        try:
            action_list = json.loads(actions_inline)
        except json.JSONDecodeError as e:
            print_error(f"parsing --actions-inline JSON: {e}")
            raise typer.Exit(2)

    result = asyncio.run(run_render(
        ctx.obj["settings"], url,
        action_list=action_list,
        include_iframes=include_iframes,
        javascript=javascript,
        referer=referer,
        geolocation=geolocation,
    ))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


# ── screenshot ────────────────────────────────────────────────────────────────

@app.command("screenshot")
def cmd_screenshot(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="URL to screenshot")],
    actions: Annotated[
        Optional[str],
        typer.Option("--actions", help="Path to a JSON file containing browser actions array"),
    ] = None,
    actions_inline: Annotated[
        Optional[str],
        typer.Option("--actions-inline", help="Inline JSON string of browser actions array"),
    ] = None,
    full_page: Annotated[bool, typer.Option("--full-page", help="Capture full scrollable page")] = False,
    image_fmt: Annotated[str, typer.Option("--format", help="Image format: jpeg or png")] = "jpeg",
    javascript: Annotated[Optional[bool], typer.Option("--javascript/--no-javascript", help="Enable/disable JavaScript")] = None,
    referer: Annotated[Optional[str], typer.Option("--referer", help="Referer header value")] = None,
    geolocation: Annotated[Optional[str], typer.Option("--geolocation", help="ISO 3166-1 alpha-2 country code")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--output-format", "-f", help="Output format")] = OutputFormat.json,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Write image/output to file")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress progress output")] = False,
) -> None:
    """Take a screenshot of a page via Zyte browser.

    When --output ends in .jpg/.jpeg/.png, the raw image bytes are written directly.
    """
    if image_fmt not in ("jpeg", "jpg", "png"):
        print_error("--format must be jpeg or png")
        raise typer.Exit(2)

    if actions and actions_inline:
        print_error("provide only one of --actions or --actions-inline")
        raise typer.Exit(2)

    action_list: list | None = None
    if actions:
        try:
            with open(actions) as f:
                action_list = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print_error(f"reading actions file: {e}")
            raise typer.Exit(2)
    elif actions_inline:
        try:
            action_list = json.loads(actions_inline)
        except json.JSONDecodeError as e:
            print_error(f"parsing --actions-inline JSON: {e}")
            raise typer.Exit(2)

    resolved_fmt = "jpeg" if image_fmt in ("jpeg", "jpg") else "png"

    result = asyncio.run(run_screenshot(
        ctx.obj["settings"], url,
        action_list=action_list,
        image_format=resolved_fmt,
        full_page=full_page,
        javascript=javascript,
        referer=referer,
        geolocation=geolocation,
    ))

    # If output is an image path, write raw bytes
    if output and Path(output).suffix.lower() in (".jpg", ".jpeg", ".png"):
        image_bytes = base64.b64decode(result["image_base64"] or "")
        with open(output, "wb") as f:
            f.write(image_bytes)
        print_info(f"Screenshot saved to {output}", quiet=quiet)
        return

    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


def run() -> None:
    """Entrypoint with top-level error handling."""
    try:
        app()
    except ZyteAPIError as e:
        print_error(str(e))
        sys.exit(e.exit_code)
    except ZyteRequestValidationError as e:
        print_error(str(e))
        sys.exit(e.exit_code)
    except RuntimeError as e:
        print_error(str(e))
        sys.exit(1)
