"""extract command group — AI extraction tools."""

from __future__ import annotations

import asyncio
from typing import Annotated, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import typer

from zyte_cli.client import ZyteClient
from zyte_cli.output import OutputFormat, print_result

app = typer.Typer(help="Extract structured data from web pages using Zyte AI.")

# Shared extract_from option type
ExtractFromArg = Annotated[
    Optional[str],
    typer.Option(
        "--from",
        help="Fetch method: auto (default), http (httpResponseBody), browser (browserHtml), browser-only (browserHtmlOnly)",
    ),
]

OutputFormatArg = Annotated[OutputFormat, typer.Option("--output-format", "-f", help="Output format")]
OutputArg = Annotated[Optional[str], typer.Option("--output", "-o", help="Write output to file")]
QuietArg = Annotated[bool, typer.Option("--quiet", "-q", help="Suppress progress output")]
GeoArg = Annotated[Optional[str], typer.Option("--geolocation", help="ISO 3166-1 alpha-2 country code")]


_EXTRACT_FROM_MAP = {
    "http": "httpResponseBody",
    "browser": "browserHtml",
    "browser-only": "browserHtmlOnly",
    "auto": None,
}


def _resolve_extract_from(value: str | None) -> str | None:
    if value is None or value == "auto":
        return None
    mapped = _EXTRACT_FROM_MAP.get(value)
    if mapped is None and value not in _EXTRACT_FROM_MAP:
        typer.echo(
            f"Error: invalid --from value '{value}'. Must be one of: auto, http, browser, browser-only",
            err=True,
        )
        raise typer.Exit(2)
    return mapped


def _build_payload(url: str, field: str, extract_from: str | None, geolocation: str | None) -> dict:
    payload: dict = {"url": url, field: True}
    if extract_from:
        payload["extractFrom"] = extract_from
    if geolocation:
        payload["geolocation"] = geolocation
    return payload


def _build_result(raw: dict, field: str, url: str) -> dict:
    return {
        "url": raw.get("url", url),
        "status_code": raw.get("statusCode"),
        "data": raw.get(field),
    }


async def _run_extraction(settings, payload: dict, field: str, url: str) -> dict:
    async with ZyteClient(settings) as client:
        raw = await client.extract(payload)
        return _build_result(raw, field, url)


@app.command("product")
def extract_product(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Product detail page URL")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract structured product data from a product detail page."""
    ef = _resolve_extract_from(extract_from)
    payload = _build_payload(url, "product", ef, geolocation)
    result = asyncio.run(_run_extraction(ctx.obj["settings"], payload, "product", url))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("product-list")
def extract_product_list(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Product listing or category page URL")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract a list of products from a product listing or category page."""
    ef = _resolve_extract_from(extract_from)
    payload = _build_payload(url, "productList", ef, geolocation)
    result = asyncio.run(_run_extraction(ctx.obj["settings"], payload, "productList", url))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("product-navigation")
def extract_product_navigation(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Product listing page URL")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract product navigation (next page, sub-categories, product links) from a listing page."""
    ef = _resolve_extract_from(extract_from)
    payload = _build_payload(url, "productNavigation", ef, geolocation)
    result = asyncio.run(_run_extraction(ctx.obj["settings"], payload, "productNavigation", url))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("article")
def extract_article(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Article or news page URL")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract structured article data (headline, author, date, body)."""
    ef = _resolve_extract_from(extract_from)
    payload = _build_payload(url, "article", ef, geolocation)
    result = asyncio.run(_run_extraction(ctx.obj["settings"], payload, "article", url))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("article-list")
def extract_article_list(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Article listing or news index page URL")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract a list of articles with summaries from a news/blog index page."""
    ef = _resolve_extract_from(extract_from)
    payload = _build_payload(url, "articleList", ef, geolocation)
    result = asyncio.run(_run_extraction(ctx.obj["settings"], payload, "articleList", url))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("article-navigation")
def extract_article_navigation(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Article listing page URL")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract article navigation (next page link, article links) from a listing page."""
    ef = _resolve_extract_from(extract_from)
    payload = _build_payload(url, "articleNavigation", ef, geolocation)
    result = asyncio.run(_run_extraction(ctx.obj["settings"], payload, "articleNavigation", url))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("page")
def extract_page(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Page URL")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract readable page content from any page."""
    ef = _resolve_extract_from(extract_from)
    payload = _build_payload(url, "pageContent", ef, geolocation)
    result = asyncio.run(_run_extraction(ctx.obj["settings"], payload, "pageContent", url))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("forum-thread")
def extract_forum_thread(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Forum thread page URL")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract forum thread data (topic and posts with reactions)."""
    ef = _resolve_extract_from(extract_from)
    payload = _build_payload(url, "forumThread", ef, geolocation)
    result = asyncio.run(_run_extraction(ctx.obj["settings"], payload, "forumThread", url))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("job-posting")
def extract_job_posting(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Job posting detail page URL")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract job posting data (title, description, salary, location, hiring org)."""
    ef = _resolve_extract_from(extract_from)
    payload = _build_payload(url, "jobPosting", ef, geolocation)
    result = asyncio.run(_run_extraction(ctx.obj["settings"], payload, "jobPosting", url))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("job-navigation")
def extract_job_navigation(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Job listing index page URL")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract job posting navigation (next page link, job links) from a listing page."""
    ef = _resolve_extract_from(extract_from)
    payload = _build_payload(url, "jobPostingNavigation", ef, geolocation)
    result = asyncio.run(_run_extraction(ctx.obj["settings"], payload, "jobPostingNavigation", url))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("serp")
def extract_serp(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Google search URL")],
    pages: Annotated[int, typer.Option("--pages", help="Number of result pages to fetch")] = 5,
    extract_from: Annotated[
        Optional[str],
        typer.Option("--from", help="Fetch method: auto (default), http, browser"),
    ] = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract Google SERP results. URL must be a Google search URL.

    Fetches multiple pages concurrently using the 'start' pagination parameter.
    """
    ef = _resolve_extract_from(extract_from)

    def _page_url(base: str, page: int) -> str:
        parsed = urlparse(base)
        params = parse_qs(parsed.query, keep_blank_values=True)
        if page == 1:
            params.pop("start", None)
        else:
            params["start"] = [str((page - 1) * 10)]
        new_query = urlencode({k: v[0] for k, v in params.items()})
        return urlunparse(parsed._replace(query=new_query))

    async def run() -> None:
        serp_options: dict = {}
        if ef:
            serp_options["extractFrom"] = ef

        async with ZyteClient(ctx.obj["settings"]) as client:
            async def fetch_page(page: int) -> dict:
                payload: dict = {
                    "url": _page_url(url, page),
                    "serp": True,
                }
                if serp_options:
                    payload["serpOptions"] = serp_options
                if geolocation:
                    payload["geolocation"] = geolocation
                return await client.extract(payload)

            pages_count = max(1, pages)
            raws = await asyncio.gather(*[fetch_page(p) for p in range(1, pages_count + 1)])

        all_results: list = []
        for raw in raws:
            serp_data = raw.get("serp") or {}
            all_results.extend(serp_data.get("organicResults") or [])

        first_serp = (raws[0].get("serp") or {}) if raws else {}
        result = {
            "url": raws[0].get("url", url) if raws else url,
            "pages_fetched": len(raws),
            "status_codes": [r.get("statusCode") for r in raws],
            "organic_results": all_results,
            "total_organic_results_count": len(all_results),
            "metadata": first_serp.get("metadata"),
        }
        print_result(result, fmt=output_format, output_file=output, quiet=quiet)

    asyncio.run(run())
