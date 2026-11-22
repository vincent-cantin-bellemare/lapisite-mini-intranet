"""The errors the client raises (handwritten).

Branch on ``status`` first, then on ``code``: ``message`` is for humans and may change. Every API error carries the
``request_id`` to quote to support and to find the call in the agency's API journal.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional


class LapisiteError(Exception):
    """Base class of every error raised by the SDK."""


class APIConnectionError(LapisiteError):
    """The request did not get an answer (DNS, connection refused or reset, TLS)."""


class APITimeoutError(APIConnectionError):
    """The request got no answer within the timeout."""


class WebhookSignatureError(LapisiteError):
    """A webhook's signature, timestamp or body was refused: answer 400 and do not trust the request."""


class APIError(LapisiteError):
    """The API answered with an error status (4xx or 5xx)."""

    def __init__(
        self,
        status: int,
        code: Optional[str],
        message: str,
        *,
        request_id: Optional[str] = None,
        param: Optional[str] = None,
        body: Any = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        super().__init__(f"{status} {code or 'error'}: {message}" + (f" (request {request_id})" if request_id else ""))
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id
        self.param = param
        self.body = body
        self.headers: Mapping[str, str] = headers or {}

    @property
    def retry_after(self) -> Optional[float]:
        """Seconds the API asked to wait (``Retry-After``), or None."""
        return parse_retry_after(self.headers.get("retry-after"))


class BadRequestError(APIError):
    """400: the request is malformed (``invalid_request``, ``invalid_body``…); fix it."""


class AuthenticationError(APIError):
    """401: no valid key (``invalid_api_key``, ``api_key_revoked``, ``api_key_expired``)."""


class PermissionDeniedError(APIError):
    """403: the key may not do this (``insufficient_scope``, ``forbidden``, ``sandbox_only``…)."""


class NotFoundError(APIError):
    """404: not found, or not visible to this key."""


class ConflictError(APIError):
    """409: conflicts with the current state (``conflict``, ``job_already_running``, ``idempotency_key_reused``)."""


class GoneError(APIError):
    """410: gone for good (``trash_expired``, ``report_gone``)."""


class UnprocessableEntityError(APIError):
    """422: valid JSON whose values are refused (``validation_failed``: see ``body['error']['errors']``)."""


class RateLimitError(APIError):
    """429: too many requests or a quota used up; ``retry_after`` says how long to wait."""


class InternalServerError(APIError):
    """5xx: retry later, with the same ``Idempotency-Key``."""


_BY_STATUS = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    410: GoneError,
    422: UnprocessableEntityError,
    429: RateLimitError,
}


def error_class(status: int) -> type[APIError]:
    """The APIError subclass for an HTTP status."""
    if status >= 500:
        return InternalServerError
    return _BY_STATUS.get(status, APIError)


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """``Retry-After`` in seconds (the API sends seconds), or None when absent or unreadable."""
    if value is None:
        return None
    try:
        seconds = float(value.strip())
    except ValueError:
        return None
    return seconds if seconds >= 0 else None
