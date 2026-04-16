"""cloud command group — Scrapy Cloud management tools."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from typing import Annotated, Optional

import typer
from scrapinghub import ScrapinghubClient

from zyte_cli.config import get_scrapy_cloud_settings
from zyte_cli.output import OutputFormat, print_result, print_error, print_verbose, print_dry_run

app = typer.Typer(help="Manage Scrapy Cloud projects, spiders, and jobs.")
jobs_app = typer.Typer(help="List, cancel, tag, and inspect Scrapy Cloud jobs. Job keys use the format <project>/<spider>/<job> (e.g. 123/1/45).")
app.add_typer(jobs_app, name="jobs")

OutputFormatArg = Annotated[OutputFormat, typer.Option("--output-format", "-f", help="Output format")]
OutputArg = Annotated[Optional[str], typer.Option("--output", "-o", help="Write output to file")]
QuietArg = Annotated[bool, typer.Option("--quiet", "-q", help="Suppress progress output")]


def _get_cloud_client(ctx: typer.Context) -> ScrapinghubClient:
    cloud_api_key = ctx.obj.get("cloud_api_key")
    settings = get_scrapy_cloud_settings(api_key_override=cloud_api_key)
    return ScrapinghubClient(settings.api_key)


@app.command("deploy")
def cloud_deploy(
    ctx: typer.Context,
    project_id: Annotated[Optional[int], typer.Option("--project-id", "-p", help="Scrapy Cloud project ID")] = None,
    quiet: QuietArg = False,
) -> None:
    """Deploy the current Scrapy project to Scrapy Cloud (wraps shub deploy).

    Requires 'shub' to be installed: pip install shub

    Run from the root of a Scrapy project directory. If --project-id is omitted,
    shub will use the project configured in scrapinghub.yml.
    """
    cmd = ["shub", "deploy"]
    if project_id is not None:
        cmd.append(str(project_id))

    dry_run = ctx.obj.get("dry_run", False)
    if dry_run:
        print_dry_run({"command": cmd}, label="DRY RUN — would run:")
        raise typer.Exit(0)

    try:
        result = subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print_error("'shub' not found. Install it with: pip install shub")
        raise typer.Exit(1)
    except subprocess.CalledProcessError as e:
        raise typer.Exit(e.returncode)


@app.command("run")
def cloud_run(
    ctx: typer.Context,
    spider: Annotated[str, typer.Argument(help="Spider name")],
    project: Annotated[int, typer.Option("--project", "-p", help="Scrapy Cloud project ID")],
    arg: Annotated[
        Optional[list[str]],
        typer.Option("--arg", "-a", help="Spider argument as key=value (repeatable)"),
    ] = None,
    setting: Annotated[
        Optional[list[str]],
        typer.Option("--setting", "-s", help="Scrapy setting as key=value (repeatable)"),
    ] = None,
    priority: Annotated[Optional[int], typer.Option("--priority", help="Job priority (0-4)")] = None,
    units: Annotated[Optional[int], typer.Option("--units", help="Number of spider units")] = None,
    tag: Annotated[Optional[list[str]], typer.Option("--tag", help="Job tag (repeatable)")] = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Run a spider job on Scrapy Cloud.

    Spider arguments and settings are passed as KEY=VALUE pairs (repeatable):

        zyte cloud run my_spider -p 12345 -a start_url=https://example.com -s CONCURRENT_REQUESTS=8

    Priority ranges from 0 (lowest) to 4 (highest). Units control how many
    parallel execution units the job uses (affects billing).

    Returns the job key (e.g. 12345/1/7) which can be used with other
    'zyte cloud jobs' and 'zyte cloud items/logs/requests' commands.
    """
    client = _get_cloud_client(ctx)

    job_args: dict = {}
    for a in arg or []:
        if "=" not in a:
            print_error(f"Invalid --arg format '{a}', expected key=value")
            raise typer.Exit(2)
        k, v = a.split("=", 1)
        job_args[k.strip()] = v.strip()

    job_settings: dict = {}
    for s in setting or []:
        if "=" not in s:
            print_error(f"Invalid --setting format '{s}', expected key=value")
            raise typer.Exit(2)
        k, v = s.split("=", 1)
        job_settings[k.strip()] = v.strip()

    kwargs: dict = {}
    if job_args:
        kwargs["job_args"] = job_args
    if job_settings:
        kwargs["job_settings"] = job_settings
    if units is not None:
        kwargs["units"] = units
    if priority is not None:
        kwargs["priority"] = priority
    if tag:
        kwargs["add_tag"] = tag

    dry_run = ctx.obj.get("dry_run", False)
    verbose = ctx.obj.get("verbose", False)

    if dry_run:
        print_dry_run(
            {"project": project, "spider": spider, **kwargs},
            label="DRY RUN — would run spider:",
        )
        raise typer.Exit(0)

    if verbose:
        print_verbose("→ Scrapy Cloud job kwargs", {"project": project, "spider": spider, **kwargs})

    def _run():
        proj = client.get_project(project)
        job = proj.jobs.run(spider, **kwargs)
        return job.key

    job_key = asyncio.run(asyncio.to_thread(_run))

    if verbose:
        print_verbose("← Job key", {"job_key": job_key})

    print_result({"job_key": job_key}, fmt=output_format, output_file=output, quiet=quiet)


@app.command("spiders")
def cloud_spiders(
    ctx: typer.Context,
    project: Annotated[int, typer.Option("--project", "-p", help="Scrapy Cloud project ID")],
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """List all deployed spiders in a Scrapy Cloud project."""
    client = _get_cloud_client(ctx)

    def _list():
        return client.get_project(project).spiders.list()

    spiders = asyncio.run(asyncio.to_thread(_list))
    print_result(
        {"project_id": project, "spiders": spiders, "count_returned": len(spiders)},
        fmt=output_format,
        output_file=output,
        quiet=quiet,
    )


@app.command("activity")
def cloud_activity(
    ctx: typer.Context,
    project: Annotated[int, typer.Option("--project", "-p", help="Scrapy Cloud project ID")],
    count: Annotated[Optional[int], typer.Option("--count", "-n", help="Max events to return")] = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Get recent activity events for a Scrapy Cloud project."""
    client = _get_cloud_client(ctx)

    def _get():
        kwargs: dict = {}
        if count is not None:
            kwargs["count"] = count
        return list(client.get_project(project).activity.iter(**kwargs))

    events = asyncio.run(asyncio.to_thread(_get))
    print_result(
        {"project_id": project, "events": events, "count_returned": len(events)},
        fmt=output_format,
        output_file=output,
        quiet=quiet,
    )


@app.command("items")
def cloud_items(
    ctx: typer.Context,
    job_key: Annotated[str, typer.Argument(help="Job key (e.g. 123/1/45)")],
    count: Annotated[Optional[int], typer.Option("--count", "-n", help="Max items to return")] = None,
    start: Annotated[Optional[int], typer.Option("--start", help="Start offset")] = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """List scraped items from a Scrapy Cloud job."""
    client = _get_cloud_client(ctx)

    def _list():
        kwargs: dict = {}
        if count is not None:
            kwargs["count"] = count
        if start is not None:
            kwargs["start"] = start
        return list(client.get_job(job_key).items.iter(**kwargs))

    items = asyncio.run(asyncio.to_thread(_list))
    print_result(
        {"job_key": job_key, "items": items, "count_returned": len(items)},
        fmt=output_format,
        output_file=output,
        quiet=quiet,
    )


@app.command("logs")
def cloud_logs(
    ctx: typer.Context,
    job_key: Annotated[str, typer.Argument(help="Job key (e.g. 123/1/45)")],
    count: Annotated[Optional[int], typer.Option("--count", "-n", help="Max log entries to return")] = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Get log entries for a Scrapy Cloud job."""
    client = _get_cloud_client(ctx)

    def _get():
        kwargs: dict = {}
        if count is not None:
            kwargs["count"] = count
        return list(client.get_job(job_key).logs.iter(**kwargs))

    logs = asyncio.run(asyncio.to_thread(_get))
    print_result(
        {"job_key": job_key, "logs": logs, "count_returned": len(logs)},
        fmt=output_format,
        output_file=output,
        quiet=quiet,
    )


@app.command("requests")
def cloud_requests(
    ctx: typer.Context,
    job_key: Annotated[str, typer.Argument(help="Job key (e.g. 123/1/45)")],
    count: Annotated[Optional[int], typer.Option("--count", "-n", help="Max request records to return")] = None,
    start: Annotated[Optional[int], typer.Option("--start", help="Start offset")] = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """List HTTP request records from a Scrapy Cloud job."""
    client = _get_cloud_client(ctx)

    def _list():
        kwargs: dict = {}
        if count is not None:
            kwargs["count"] = count
        if start is not None:
            kwargs["start"] = start
        return list(client.get_job(job_key).requests.iter(**kwargs))

    reqs = asyncio.run(asyncio.to_thread(_list))
    print_result(
        {"job_key": job_key, "requests": reqs, "count_returned": len(reqs)},
        fmt=output_format,
        output_file=output,
        quiet=quiet,
    )


# --- jobs subcommands ---

@jobs_app.command("list")
def jobs_list(
    ctx: typer.Context,
    project: Annotated[int, typer.Option("--project", "-p", help="Scrapy Cloud project ID")],
    spider: Annotated[Optional[str], typer.Option("--spider", help="Filter by spider name")] = None,
    state: Annotated[Optional[str], typer.Option("--state", help="Filter by state: pending, running, finished, deleted")] = None,
    tag: Annotated[Optional[list[str]], typer.Option("--tag", help="Filter by tag (repeatable)")] = None,
    lacks_tag: Annotated[Optional[list[str]], typer.Option("--lacks-tag", help="Exclude jobs with tag (repeatable)")] = None,
    count: Annotated[Optional[int], typer.Option("--count", "-n", help="Max jobs to return")] = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """List jobs for a Scrapy Cloud project."""
    client = _get_cloud_client(ctx)

    def _list():
        proj = client.get_project(project)
        kwargs: dict = {}
        if spider is not None:
            kwargs["spider"] = spider
        if state is not None:
            kwargs["state"] = state
        if tag is not None:
            kwargs["has_tag"] = tag
        if lacks_tag is not None:
            kwargs["lacks_tag"] = lacks_tag
        if count is not None:
            kwargs["count"] = count
        return list(proj.jobs.iter(**kwargs))

    jobs = asyncio.run(asyncio.to_thread(_list))
    print_result(
        {"jobs": jobs, "count_returned": len(jobs)},
        fmt=output_format,
        output_file=output,
        quiet=quiet,
    )


@jobs_app.command("cancel")
def jobs_cancel(
    ctx: typer.Context,
    job_key: Annotated[str, typer.Argument(help="Job key (e.g. 123/1/45)")],
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Cancel a running or pending Scrapy Cloud job."""
    client = _get_cloud_client(ctx)

    def _cancel():
        client.get_job(job_key).cancel()

    asyncio.run(asyncio.to_thread(_cancel))
    print_result({"job_key": job_key, "cancelled": True}, fmt=output_format, output_file=output, quiet=quiet)


@jobs_app.command("tags")
def jobs_tags(
    ctx: typer.Context,
    job_key: Annotated[str, typer.Argument(help="Job key (e.g. 123/1/45)")],
    add: Annotated[Optional[list[str]], typer.Option("--add", help="Tag to add (repeatable)")] = None,
    remove: Annotated[Optional[list[str]], typer.Option("--remove", help="Tag to remove (repeatable)")] = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Add or remove tags on a Scrapy Cloud job."""
    if not add and not remove:
        print_error("At least one of --add or --remove must be provided")
        raise typer.Exit(2)

    client = _get_cloud_client(ctx)

    def _update():
        kwargs: dict = {}
        if add:
            kwargs["add"] = add
        if remove:
            kwargs["remove"] = remove
        client.get_job(job_key).update_tags(**kwargs)

    asyncio.run(asyncio.to_thread(_update))
    print_result({"job_key": job_key, "updated": True}, fmt=output_format, output_file=output, quiet=quiet)


@jobs_app.command("metadata")
def jobs_metadata(
    ctx: typer.Context,
    job_key: Annotated[str, typer.Argument(help="Job key (e.g. 123/1/45)")],
    field: Annotated[Optional[str], typer.Option("--field", "-k", help="Return a single metadata field")] = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Get metadata for a Scrapy Cloud job. Use --field to return a single key."""
    client = _get_cloud_client(ctx)

    def _get():
        job = client.get_job(job_key)
        if field:
            return {"job_key": job_key, "field": field, "value": job.metadata.get(field)}
        return {"job_key": job_key, "metadata": dict(job.metadata.iter())}

    result = asyncio.run(asyncio.to_thread(_get))
    print_result(result, fmt=output_format, output_file=output, quiet=quiet)


@jobs_app.command("count")
def jobs_count(
    ctx: typer.Context,
    project: Annotated[int, typer.Option("--project", "-p", help="Scrapy Cloud project ID")],
    spider: Annotated[Optional[str], typer.Option("--spider", help="Filter by spider name")] = None,
    state: Annotated[Optional[str], typer.Option("--state", help="Filter by state")] = None,
    tag: Annotated[Optional[list[str]], typer.Option("--tag", help="Filter by tag (repeatable)")] = None,
    lacks_tag: Annotated[Optional[list[str]], typer.Option("--lacks-tag", help="Exclude jobs with tag (repeatable)")] = None,
    output_format: OutputFormatArg = OutputFormat.json,
    output: OutputArg = None,
    quiet: QuietArg = False,
) -> None:
    """Count jobs for a Scrapy Cloud project."""
    client = _get_cloud_client(ctx)

    def _count():
        proj = client.get_project(project)
        kwargs: dict = {}
        if spider is not None:
            kwargs["spider"] = spider
        if state is not None:
            kwargs["state"] = state
        if tag is not None:
            kwargs["has_tag"] = tag
        if lacks_tag is not None:
            kwargs["lacks_tag"] = lacks_tag
        return proj.jobs.count(**kwargs)

    n = asyncio.run(asyncio.to_thread(_count))
    print_result({"project_id": project, "count": n}, fmt=output_format, output_file=output, quiet=quiet)
