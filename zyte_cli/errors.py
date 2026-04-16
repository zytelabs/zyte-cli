"""Error types, exit codes, and helpers for Zyte CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Exit codes
EXIT_SUCCESS = 0
EXIT_API_ERROR = 1
EXIT_VALIDATION_ERROR = 2
EXIT_AUTH_ERROR = 3


@dataclass(slots=True)
class ZyteAPIError(Exception):
    status_code: int
    error_type: str | None
    detail: str
    payload: dict[str, Any] | None = None

    def __str__(self) -> str:
        if self.error_type:
            return f"Zyte API error {self.status_code} ({self.error_type}): {self.detail}"
        return f"Zyte API error {self.status_code}: {self.detail}"

    @property
    def exit_code(self) -> int:
        if self.status_code in {401, 403}:
            return EXIT_AUTH_ERROR
        return EXIT_API_ERROR


@dataclass(slots=True)
class ZyteRequestValidationError(Exception):
    detail: str

    def __str__(self) -> str:
        return self.detail

    @property
    def exit_code(self) -> int:
        return EXIT_VALIDATION_ERROR


def build_zyte_error(status_code: int, payload: dict[str, Any] | None) -> ZyteAPIError:
    payload = payload or {}
    error_type = payload.get("type")
    detail = payload.get("detail") or payload.get("title") or "Request failed"
    return ZyteAPIError(
        status_code=status_code,
        error_type=error_type,
        detail=detail,
        payload=payload,
    )


def is_retryable_error(status_code: int, error_type: str | None) -> bool:
    if status_code in {429, 503}:
        return True
    if status_code == 520:
        return True
    if status_code == 521 and error_type == "/download/internal-error":
        return True
    return False
