"""Configuration for the Zyte CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ZyteSettings:
    api_key: str
    base_url: str = "https://api.zyte.com/v1/extract"
    request_timeout_seconds: float = 120.0
    rate_limit_max_retries: int = 8
    download_error_max_retries: int = 3


@dataclass(frozen=True)
class ScrapyCloudSettings:
    api_key: str


def get_settings(api_key_override: str | None = None) -> ZyteSettings:
    api_key = (api_key_override or os.getenv("ZYTE_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError(
            "ZYTE_API_KEY is required. Set it as an environment variable or pass --api-key."
        )
    return ZyteSettings(api_key=api_key)


def get_scrapy_cloud_settings(api_key_override: str | None = None) -> ScrapyCloudSettings:
    api_key = (
        api_key_override
        or os.getenv("SCRAPY_CLOUD_API_KEY", "").strip()
        or os.getenv("SHUB_APIKEY", "").strip()
    )
    if not api_key:
        raise RuntimeError(
            "SCRAPY_CLOUD_API_KEY (or SHUB_APIKEY) is required for cloud commands. "
            "Set it as an environment variable or pass --cloud-api-key."
        )
    return ScrapyCloudSettings(api_key=api_key)
