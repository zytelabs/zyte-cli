"""extract command group — AI extraction tools."""

from __future__ import annotations

import asyncio
from typing import Annotated, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import typer

from zyte_cli.client import ZyteClient
from zyte_cli.output import OutputFormat, print_result, progress_spinner

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
OutputUrlsArg = Annotated[
    bool,
    typer.Option(
        "--output-urls",
        help="Print item URLs one per line instead of JSON (pipe-friendly). "
             "Multiple listing pages aggregate all URLs.",
    ),
]
NextPageUrlArg = Annotated[
    bool,
    typer.Option(
        "--next-page-url",
        help="Print the next page URL only (exits 1 if there is no next page). "
             "Useful for crawl loops.",
    ),
]


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


async def _run_extractions(
    settings,
    urls: list[str],
    field: str,
    extract_from: str | None,
    geolocation: str | None,
    quiet: bool = False,
) -> dict | list[dict]:
    ef = _resolve_extract_from(extract_from)
    total = len(urls)
    completed = 0
    lock = asyncio.Lock()

    with progress_spinner(
        f"Extracting {field} from {total} URL{'s' if total != 1 else ''}...",
        quiet=quiet or total == 1,
    ) as spinner:
        async with ZyteClient(settings) as client:

            async def _fetch(url: str) -> dict:
                nonlocal completed
                payload = _build_payload(url, field, ef, geolocation)
                raw = await client.extract(payload)
                async with lock:
                    completed += 1
                    if total > 1:
                        spinner.update(f"Extracting {field}... {completed}/{total} done")
                return _build_result(raw, field, url)

            results = await asyncio.gather(*[_fetch(u) for u in urls])
    return results[0] if len(results) == 1 else list(results)


def _print_output_urls(result: dict | list[dict]) -> None:
    """Print item URLs one per line from one or more navigation results."""
    results = result if isinstance(result, list) else [result]
    for r in results:
        data = r.get("data") or {}
        for item in data.get("items") or []:
            url = item.get("url")
            if url:
                print(url)


def _print_next_page_url(result: dict | list[dict]) -> None:
    """Print the next page URL from the first navigation result, or exit 1 if absent."""
    first = result[0] if isinstance(result, list) else result
    data = first.get("data") or {}
    next_url = (data.get("nextPage") or {}).get("url", "")
    if next_url:
        print(next_url)
    else:
        raise typer.Exit(1)


@app.command("product")
def extract_product(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Product detail page URL(s)")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract structured product data from one or more product detail pages.

    Pass multiple URLs to fetch concurrently and receive a JSON array of results.
    """
    result = asyncio.run(_run_extractions(ctx.obj["settings"], urls, "product", extract_from, geolocation, quiet=quiet))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("product-list")
def extract_product_list(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Product listing or category page URL(s)")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract a list of products from one or more product listing or category pages.

    Pass multiple URLs to fetch concurrently and receive a JSON array of results.
    """
    result = asyncio.run(_run_extractions(ctx.obj["settings"], urls, "productList", extract_from, geolocation, quiet=quiet))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("product-navigation")
def extract_product_navigation(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Product listing page URL(s)")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
    output_urls: OutputUrlsArg = False,
    next_page_url: NextPageUrlArg = False,
) -> None:
    """Extract product navigation (next page, sub-categories, product links) from one or more listing pages.

    Pass multiple URLs to fetch concurrently and receive a JSON array of results.

    Use --output-urls to get a newline-delimited list of product URLs for piping:

        zyte extract product-navigation https://shop.com/phones --output-urls \\
          | xargs zyte extract product

    Use --next-page-url to get just the next pagination URL (exits 1 if no next page):

        URL=$(zyte extract product-navigation https://shop.com/phones --next-page-url) || break
    """
    result = asyncio.run(_run_extractions(ctx.obj["settings"], urls, "productNavigation", extract_from, geolocation, quiet=quiet))
    if output_urls:
        _print_output_urls(result)
        return
    if next_page_url:
        _print_next_page_url(result)
        return
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("article")
def extract_article(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Article or news page URL(s)")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract structured article data (headline, author, date, body) from one or more pages.

    Pass multiple URLs to fetch concurrently and receive a JSON array of results.
    """
    result = asyncio.run(_run_extractions(ctx.obj["settings"], urls, "article", extract_from, geolocation, quiet=quiet))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("article-list")
def extract_article_list(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Article listing or news index page URL(s)")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract a list of articles with summaries from one or more news/blog index pages.

    Pass multiple URLs to fetch concurrently and receive a JSON array of results.
    """
    result = asyncio.run(_run_extractions(ctx.obj["settings"], urls, "articleList", extract_from, geolocation, quiet=quiet))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("article-navigation")
def extract_article_navigation(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Article listing page URL(s)")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
    output_urls: OutputUrlsArg = False,
    next_page_url: NextPageUrlArg = False,
) -> None:
    """Extract article navigation (next page link, article links) from one or more listing pages.

    Pass multiple URLs to fetch concurrently and receive a JSON array of results.

    Use --output-urls to get a newline-delimited list of article URLs for piping:

        zyte extract article-navigation https://blog.com/posts --output-urls \\
          | xargs zyte extract article

    Use --next-page-url to get just the next pagination URL (exits 1 if no next page).
    """
    result = asyncio.run(_run_extractions(ctx.obj["settings"], urls, "articleNavigation", extract_from, geolocation, quiet=quiet))
    if output_urls:
        _print_output_urls(result)
        return
    if next_page_url:
        _print_next_page_url(result)
        return
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("page")
def extract_page(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Page URL(s)")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract readable page content from one or more pages.

    Pass multiple URLs to fetch concurrently and receive a JSON array of results.
    """
    result = asyncio.run(_run_extractions(ctx.obj["settings"], urls, "pageContent", extract_from, geolocation, quiet=quiet))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("forum-thread")
def extract_forum_thread(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Forum thread page URL(s)")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract forum thread data (topic and posts with reactions) from one or more threads.

    Pass multiple URLs to fetch concurrently and receive a JSON array of results.
    """
    result = asyncio.run(_run_extractions(ctx.obj["settings"], urls, "forumThread", extract_from, geolocation, quiet=quiet))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("job-posting")
def extract_job_posting(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Job posting detail page URL(s)")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Extract job posting data (title, description, salary, location, hiring org) from one or more pages.

    Pass multiple URLs to fetch concurrently and receive a JSON array of results.
    """
    result = asyncio.run(_run_extractions(ctx.obj["settings"], urls, "jobPosting", extract_from, geolocation, quiet=quiet))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@app.command("job-navigation")
def extract_job_navigation(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Job listing index page URL(s)")],
    extract_from: ExtractFromArg = None,
    geolocation: GeoArg = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
    output_urls: OutputUrlsArg = False,
    next_page_url: NextPageUrlArg = False,
) -> None:
    """Extract job posting navigation (next page link, job links) from one or more listing pages.

    Pass multiple URLs to fetch concurrently and receive a JSON array of results.

    Use --output-urls to get a newline-delimited list of job URLs for piping:

        zyte extract job-navigation https://jobs.com/engineering --output-urls \\
          | xargs zyte extract job-posting

    Use --next-page-url to get just the next pagination URL (exits 1 if no next page).
    """
    result = asyncio.run(_run_extractions(ctx.obj["settings"], urls, "jobPostingNavigation", extract_from, geolocation, quiet=quiet))
    if output_urls:
        _print_output_urls(result)
        return
    if next_page_url:
        _print_next_page_url(result)
        return
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

        pages_count = max(1, pages)
        completed = 0
        lock = asyncio.Lock()

        with progress_spinner(
            f"Fetching SERP page 1/{pages_count}...",
            quiet=quiet or pages_count == 1,
        ) as spinner:
            async with ZyteClient(ctx.obj["settings"]) as client:
                async def fetch_page(page: int) -> dict:
                    nonlocal completed
                    payload: dict = {
                        "url": _page_url(url, page),
                        "serp": True,
                    }
                    if serp_options:
                        payload["serpOptions"] = serp_options
                    if geolocation:
                        payload["geolocation"] = geolocation
                    result = await client.extract(payload)
                    async with lock:
                        completed += 1
                        spinner.update(f"Fetching SERP... {completed}/{pages_count} pages done")
                    return result

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
