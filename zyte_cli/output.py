"""Output rendering for the Zyte CLI."""

from __future__ import annotations

import csv
import io
import json
import os
import sys
from enum import Enum
from typing import Any

from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table


class OutputFormat(str, Enum):
    json = "json"
    pretty = "pretty"
    table = "table"
    csv = "csv"


def _no_color_enabled() -> bool:
    """Return True if color should be disabled (NO_COLOR env var or explicit flag)."""
    return "NO_COLOR" in os.environ


_no_color = _no_color_enabled()
_err_console = Console(stderr=True, no_color=_no_color)
_out_console = Console(no_color=_no_color)


def configure_color(no_color: bool) -> None:
    """Re-initialise module-level consoles. Call after parsing --no-color."""
    global _no_color, _err_console, _out_console
    _no_color = no_color
    _err_console = Console(stderr=True, no_color=no_color)
    _out_console = Console(no_color=no_color)


def print_result(
    data: Any,
    *,
    fmt: OutputFormat = OutputFormat.json,
    output_file: str | None = None,
    quiet: bool = False,
) -> None:
    """Render data to stdout or a file."""
    rendered = _render(data, fmt=fmt)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(rendered)
        if not quiet:
            _err_console.print(f"[green]Output written to {output_file}[/green]")
    else:
        if fmt == OutputFormat.pretty:
            _out_console.print(Syntax(rendered, "json", theme="monokai", word_wrap=True))
        else:
            print(rendered)


def print_error(message: str) -> None:
    _err_console.print(f"[bold red]Error:[/bold red] {message}", highlight=False)


def print_info(message: str, quiet: bool = False) -> None:
    if not quiet:
        _err_console.print(f"[dim]{message}[/dim]")


def print_verbose(label: str, data: Any) -> None:
    """Print a verbose section header and pretty JSON payload to stderr."""
    rendered = json.dumps(data, indent=2, default=str)
    _err_console.print(f"\n[bold cyan]{label}[/bold cyan]")
    _err_console.print(Syntax(rendered, "json", theme="monokai", word_wrap=True))


def print_dry_run(payload: Any, label: str = "DRY RUN — would send to Zyte API:") -> None:
    """Print the payload that would be sent, without making the request."""
    rendered = json.dumps(payload, indent=2, default=str)
    _err_console.print(f"\n[bold yellow]{label}[/bold yellow]")
    _err_console.print(Syntax(rendered, "json", theme="monokai", word_wrap=True))


def _render(data: Any, fmt: OutputFormat) -> str:
    if fmt in (OutputFormat.json, OutputFormat.pretty):
        return json.dumps(data, indent=2, default=str)
    elif fmt == OutputFormat.table:
        return _render_table(data)
    elif fmt == OutputFormat.csv:
        return _render_csv(data)
    return json.dumps(data, indent=2, default=str)


def _render_table(data: Any) -> str:
    """Render a list of dicts as an ASCII table using Rich, falling back to JSON."""
    rows: list[dict] | None = None

    if isinstance(data, list) and data and isinstance(data[0], dict):
        rows = data
    elif isinstance(data, dict):
        # Try common list keys
        for key in ("jobs", "items", "events", "spiders", "organic_results", "requests", "logs"):
            if key in data and isinstance(data[key], list):
                rows = data[key]
                break

    if not rows:
        return json.dumps(data, indent=2, default=str)

    columns = list(rows[0].keys())
    table = Table(*columns, show_header=True, header_style="bold cyan")
    for row in rows:
        table.add_row(*[str(row.get(c, "")) for c in columns])

    buf = io.StringIO()
    console = Console(file=buf, highlight=False)
    console.print(table)
    return buf.getvalue()


def _render_csv(data: Any) -> str:
    """Render a list of dicts as CSV, falling back to JSON."""
    rows: list[dict] | None = None

    if isinstance(data, list) and data and isinstance(data[0], dict):
        rows = data
    elif isinstance(data, dict):
        for key in ("jobs", "items", "events", "spiders", "organic_results", "requests", "logs"):
            if key in data and isinstance(data[key], list):
                rows = data[key]
                break

    if not rows:
        return json.dumps(data, indent=2, default=str)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()
