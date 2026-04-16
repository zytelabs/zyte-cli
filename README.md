# zyte-cli

> **Community project** — This is not an official Zyte product and is not maintained or supported by Zyte. For official support, refer to the [Zyte documentation](https://docs.zyte.com) or [Zyte support channels](https://www.zyte.com/contact/).

A command-line interface for the [Zyte API](https://docs.zyte.com/zyte-api/get-started.html) and [Scrapy Cloud](https://docs.zyte.com/scrapy-cloud.html). Fetch pages, render JavaScript, take screenshots, extract structured data with AI, and manage cloud spider jobs — all from your terminal.

## Installation

Not available on PyPI. Install from source using [uv](https://docs.astral.sh/uv/) (requires Python 3.13+):

```bash
git clone https://github.com/zytelabs/zyte-cli /tmp/zyte-cli && uv tool install /tmp/zyte-cli
```

Verify the install:

```bash
zyte --help
```

## Authentication

Set your Zyte API key as an environment variable:

```bash
export ZYTE_API_KEY=your_api_key_here
```

For Scrapy Cloud commands, also set:

```bash
export SCRAPY_CLOUD_API_KEY=your_scrapy_cloud_key
# or
export SHUB_APIKEY=your_scrapy_cloud_key
```

Both keys can also be passed inline per-command with `--api-key` and `--cloud-api-key`.

## Commands

### `zyte fetch` — HTTP fetch

Fetch a URL using Zyte's HTTP mode. No browser or JavaScript — fast, cheap, ideal for APIs, sitemaps, and static HTML.

```bash
# Basic GET
zyte fetch "https://httpbin.org/get"

# POST with a JSON body
zyte fetch "https://httpbin.org/post" \
  --method POST \
  --body-text '{"query": "hello"}' \
  --header "Accept=application/json"

# Fetch from a specific country
zyte fetch "https://example.com" --geolocation US

# Save the response to a file
zyte fetch "https://example.com" --output response.json
```

**Options:**

| Flag | Description |
|---|---|
| `-X, --method` | HTTP method (default: `GET`) |
| `-H, --header` | Request header as `key=value` (repeatable) |
| `--body-text` | Request body as plain text |
| `--body-base64` | Request body as base64-encoded bytes |
| `--geolocation` | ISO 3166-1 alpha-2 country code (e.g. `US`, `DE`) |
| `-f, --output-format` | Output format: `json` (default), `pretty`, `table`, `csv` |
| `-o, --output` | Write output to a file |
| `-q, --quiet` | Suppress progress output |

---

### `zyte render` — Browser render

Render a page in a real browser with full JavaScript execution and return the final HTML.

```bash
# Render a page
zyte render "https://example.com"

# Render and save the HTML
zyte render "https://example.com" --output page.html

# Render as pretty-printed output
zyte render "https://example.com" --output-format pretty
```

---

### `zyte screenshot` — Browser screenshot

Take a JPEG or PNG screenshot of a page via the Zyte browser.

```bash
# Save a JPEG screenshot
zyte screenshot "https://example.com" --output screenshot.jpg

# Save a full-page PNG screenshot
zyte screenshot "https://example.com" --output screenshot.png --full-page

# Return screenshot as base64 JSON (default when no --output is given)
zyte screenshot "https://example.com"
```

When `--output` ends in `.jpg`, `.jpeg`, or `.png`, the image bytes are written directly to the file. Otherwise, the result is JSON with a base64-encoded `screenshot` field.

---

### `zyte extract` — AI data extraction

Extract structured data from web pages using Zyte's AI extraction engine. All subcommands accept a `--from` flag to control the fetch method.

**`--from` values:**

| Value | Description |
|---|---|
| `auto` (default) | Zyte API chooses the best method |
| `http` | Force HTTP fetch (`httpResponseBody`) |
| `browser` | Force browser render (`browserHtml`) |
| `browser-only` | Browser render only, no fallback (`browserHtmlOnly`) |

#### Products

```bash
# Extract a single product
zyte extract product "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"

# Extract product list from a category page
zyte extract product-list "https://books.toscrape.com/"

# Extract navigation links from a category page (next page, sub-categories, product URLs)
zyte extract product-navigation "https://books.toscrape.com/"
```

#### Articles

```bash
# Extract a single article
zyte extract article "https://www.bbc.com/news/articles/example"

# Extract article list from a news index
zyte extract article-list "https://www.bbc.com/news"

# Extract navigation links from a news listing page
zyte extract article-navigation "https://www.bbc.com/news"
```

#### Other page types

```bash
# Extract readable content from any page
zyte extract page "https://en.wikipedia.org/wiki/Web_scraping"

# Extract a forum thread (topic + posts)
zyte extract forum-thread "https://forum.example.com/thread/123"

# Extract a job posting
zyte extract job-posting "https://jobs.example.com/position/456"

# Extract job navigation links from a job board listing
zyte extract job-navigation "https://jobs.example.com/"
```

#### Google SERP

```bash
# Extract organic results from a Google search (fetches 5 pages by default)
zyte extract serp "https://www.google.com/search?q=web+scraping+python"

# Fetch only 2 pages of results
zyte extract serp "https://www.google.com/search?q=scrapy" --pages 2
```

#### Output options (all extract subcommands)

```bash
# Pretty-print with Rich
zyte extract product "https://..." --output-format pretty

# Render as a table
zyte extract product-list "https://..." --output-format table

# Write JSON to a file silently
zyte extract product "https://..." --output product.json --quiet

# Force HTTP fetch method
zyte extract article "https://..." --from http

# Restrict to a specific country
zyte extract product "https://..." --geolocation DE
```

---

### `zyte cloud` — Scrapy Cloud management

Manage Scrapy Cloud projects, spiders, and jobs. Requires `SCRAPY_CLOUD_API_KEY` or `SHUB_APIKEY`.

#### Deploy and run

```bash
# Deploy the current Scrapy project to Scrapy Cloud (wraps shub deploy)
zyte cloud deploy --project 12345

# List spiders deployed in a project
zyte cloud spiders --project 12345

# Run a spider
zyte cloud run --project 12345 --spider my_spider

# Run a spider with arguments and custom settings
zyte cloud run --project 12345 --spider my_spider \
  --arg start_url=https://example.com \
  --setting CONCURRENT_REQUESTS=8
```

#### Job management

```bash
# List recent jobs
zyte cloud jobs list --project 12345

# List only running jobs
zyte cloud jobs list --project 12345 --state running

# Count pending jobs
zyte cloud jobs count --project 12345 --state pending

# Cancel a job
zyte cloud jobs cancel 12345/1/7

# Add tags to a job
zyte cloud jobs tags 12345/1/7 --add reviewed --add approved

# Remove a tag
zyte cloud jobs tags 12345/1/7 --remove stale

# Get full job metadata
zyte cloud jobs metadata 12345/1/7

# Get a single metadata field
zyte cloud jobs metadata 12345/1/7 --field state
```

#### Job data

```bash
# List scraped items from a finished job
zyte cloud items 12345/1/7

# Get the first 50 items
zyte cloud items 12345/1/7 --count 50

# Get log entries
zyte cloud logs 12345/1/7

# List HTTP requests made during a job
zyte cloud requests 12345/1/7

# Get recent project activity
zyte cloud activity --project 12345
```

---

## Output formats

All commands support `-f` / `--output-format`:

| Format | Description |
|---|---|
| `json` | Compact JSON (default) |
| `pretty` | Human-readable JSON with Rich highlighting |
| `table` | Tabular view (best for list results) |
| `csv` | CSV (best for list results) |

Use `-o` / `--output` to write output to a file instead of stdout. Use `-q` / `--quiet` to suppress all non-result output.

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | API error (unexpected response, network error, etc.) |
| `2` | Invalid request (bad arguments or payload) |
| `3` | Authentication error (missing or invalid API key) |

---

## Environment variables

| Variable | Description |
|---|---|
| `ZYTE_API_KEY` | Zyte API key (required for all non-cloud commands) |
| `SCRAPY_CLOUD_API_KEY` | Scrapy Cloud API key (required for `zyte cloud` commands) |
| `SHUB_APIKEY` | Alternative Scrapy Cloud API key variable |
