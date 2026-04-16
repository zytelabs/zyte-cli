"""Output rendering for the Zyte CLI."""

from __future__ import annotations

import csv
import io
import json
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


_err_console = Console(stderr=True)
_out_console = Console()


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
