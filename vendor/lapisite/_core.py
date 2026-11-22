"""The HTTP core of the client (handwritten; the operations in ``_operations.py`` are generated).

- the key: ``Authorization: Bearer lps_…``;
- ``Idempotency-Key``: generated (UUID v4) when an operation takes one and the caller gave none, and the SAME key is
  sent again on every retry of that call;
- retries: on a network failure, ``429`` and ``5xx``, after ``Retry-After`` when the API sends it (else exponential
  backoff with jitter). A write is retried only when it is safe: it carries an ``Idempotency-Key``, or the API refused
  it before doing anything (``429``). A ``Retry-After`` longer than ``max_retry_wait`` is not waited for;
- pagination: the three shapes of the API (``data``/``has_more``/``next_cursor`` for Studio, ``next_before`` for
  Audits, ``items``/``next_cursor`` for Leads), read from each operation's description.

No dependency outside the standard library.
"""

from __future__ import annotations

import json
import os
import random
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, Mapping, Optional, Tuple, TypedDict

from ._version import __version__
from .errors import APIConnectionError, APITimeoutError, error_class, parse_retry_after

DEFAULT_BASE_URL = "https://api.lapisite.com"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_RETRY_WAIT = 60.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
SAFE_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE"})


@dataclass(frozen=True)
class Operation:
    """How to call one operation of the contract (generated, one per operationId)."""

    id: str
    method: str
    path: str
    idempotency: Optional[str] = None  # "required", "optional" or None
    body: Optional[str] = None  # "json", "multipart" or None
    answer: str = "json"  # "json", "text", "binary" or "none"
    page: Optional[Tuple[str, str, str, Optional[str]]] = None  # (query param, next field, items field, has_more field)


class RequestOptions(TypedDict, total=False):
    """Per-call overrides."""

    timeout: float
    max_retries: int
    headers: Mapping[str, str]


class Headers(Dict[str, str]):
    """Response headers, names in lowercase."""

    def __init__(self, items: Any = ()) -> None:
        super().__init__()
        for name, value in dict(items).items() if isinstance(items, Mapping) else items:
            self[name.lower()] = value

    def get(self, name: str, default: Any = None) -> Any:  # type: ignore[override]
        return super().get(name.lower(), default)


@dataclass
class Request:
    method: str
    url: str
    headers: Dict[str, str]
    body: Optional[bytes]
    timeout: float


@dataclass
class Response:
    status: int
    headers: Headers
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8")) if self.body else None

    @property
    def request_id(self) -> Optional[str]:
        return self.headers.get("x-request-id")

    @property
    def replayed(self) -> bool:
        """True when this is the stored first answer to the same ``Idempotency-Key``."""
        return self.headers.get("idempotent-replayed") == "true"


Transport = Callable[[Request], Response]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def urllib_transport(request: Request) -> Response:
    """The default transport: urllib from the standard library, no redirect followed."""
    raw = urllib.request.Request(request.url, data=request.body, method=request.method, headers=request.headers)
    try:
        with _OPENER.open(raw, timeout=request.timeout) as answer:
            return Response(answer.status, Headers(answer.headers.items()), answer.read())
    except urllib.error.HTTPError as error:
        return Response(error.code, Headers(error.headers.items()), error.read())
    except (socket.timeout, TimeoutError) as error:
        raise APITimeoutError(f"{request.method} {request.url}: no answer within {request.timeout:g} s") from error
    except (urllib.error.URLError, OSError) as error:
        raise APIConnectionError(f"{request.method} {request.url}: {error}") from error


def _query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(_query_value(v) for v in value)
    return str(value)


def _multipart(fields: Mapping[str, Any]) -> Tuple[bytes, str]:
    """A multipart/form-data body. A file is bytes, a binary file object, or (filename, bytes or file, content type)."""
    boundary = f"lapisite-{uuid.uuid4().hex}"
    out = bytearray()
    for name, value in fields.items():
        if value is None:
            continue
        filename, content_type = None, None
        if isinstance(value, tuple):
            filename, value, content_type = (value + (None,))[:3]
        if hasattr(value, "read"):
            filename = filename or os.path.basename(str(getattr(value, "name", name)))
            value = value.read()
        if isinstance(value, (bytes, bytearray)):
            filename = filename or name
            content_type = content_type or "application/octet-stream"
        out += f"--{boundary}\r\n".encode()
        disposition = f'form-data; name="{name}"' + (f'; filename="{filename}"' if filename else "")
        out += f"Content-Disposition: {disposition}\r\n".encode()
        if content_type:
            out += f"Content-Type: {content_type}\r\n".encode()
        out += b"\r\n"
        out += bytes(value) if isinstance(value, (bytes, bytearray)) else str(value).encode("utf-8")
        out += b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


class Client:
    """The HTTP core shared by the products (``Lapisite`` adds ``studio``, ``audits`` and ``leads``)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        language: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_retry_wait: float = DEFAULT_MAX_RETRY_WAIT,
        transport: Optional[Transport] = None,
        user_agent: Optional[str] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ.get("LAPISITE_API_KEY")
        if not key:
            raise ValueError("an API key is required: Lapisite(api_key=...) or the LAPISITE_API_KEY variable")
        self.api_key = key
        self.base_url = (base_url or os.environ.get("LAPISITE_API_BASE") or DEFAULT_BASE_URL).rstrip("/")
        self.language = language
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_retry_wait = max_retry_wait
        self.transport: Transport = transport or urllib_transport
        self.user_agent = user_agent or f"lapisite-python/{__version__}"
        self._sleep = sleep
        self._local = threading.local()

    @property
    def last_response(self) -> Optional[Response]:
        """The last answer this thread received (headers such as ``X-Request-Id``, ``Idempotent-Replayed``)."""
        return getattr(self._local, "response", None)

    # --- one call -------------------------------------------------------------------------------------------------
    def call(
        self,
        op: Operation,
        *,
        path: Optional[Mapping[str, Any]] = None,
        query: Optional[Mapping[str, Any]] = None,
        body: Any = None,
        idempotency_key: Optional[str] = None,
        accept_language: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Any:
        """Sends one operation, with its retries, and returns the decoded answer (or raises an ``APIError``)."""
        response = self.send(op, path=path, query=query, body=body, idempotency_key=idempotency_key,
                             accept_language=accept_language, options=options)
        if op.answer == "json":
            return response.json()
        if op.answer == "text":
            return response.body.decode("utf-8")
        if op.answer == "binary":
            return response.body
        # The contract declares no content: still hand back a JSON answer when one comes.
        if response.body and "json" in (response.headers.get("content-type") or ""):
            return response.json()
        return None

    def send(
        self,
        op: Operation,
        *,
        path: Optional[Mapping[str, Any]] = None,
        query: Optional[Mapping[str, Any]] = None,
        body: Any = None,
        idempotency_key: Optional[str] = None,
        accept_language: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Response:
        """Like ``call`` but returns the raw ``Response``."""
        options = options or {}
        url = self.base_url + self._path(op, path or {})
        params = [(k, _query_value(v)) for k, v in (query or {}).items() if v is not None]
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        language = accept_language or self.language
        if language:
            headers["Accept-Language"] = language
        if op.idempotency:
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
        data: Optional[bytes] = None
        if body is not None:
            if op.body == "multipart":
                data, headers["Content-Type"] = _multipart(body)
            else:
                data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                headers["Content-Type"] = "application/json"
        headers.update(options.get("headers") or {})
        request = Request(op.method, url, headers, data, float(options.get("timeout", self.timeout)))
        retry_safe = op.method in SAFE_METHODS or "Idempotency-Key" in headers
        return self._send_with_retries(request, retry_safe, int(options.get("max_retries", self.max_retries)))

    @staticmethod
    def _path(op: Operation, values: Mapping[str, Any]) -> str:
        out = op.path
        for name, value in values.items():
            if value is None:
                raise ValueError(f"{op.id}: the path parameter {name} is required")
            out = out.replace("{" + name + "}", urllib.parse.quote(str(value), safe=""))
        return out

    def _backoff(self, attempt: int) -> float:
        return float(min(8.0, 0.5 * 2**attempt) * (0.5 + random.random() / 2))

    def _send_with_retries(self, request: Request, retry_safe: bool, max_retries: int) -> Response:
        attempt = 0
        while True:
            try:
                response = self.transport(request)
            except APIConnectionError:
                if not retry_safe or attempt >= max_retries:
                    raise
                self._sleep(self._backoff(attempt))
                attempt += 1
                continue
            self._local.response = response
            if response.status < 400:
                return response
            wait = parse_retry_after(response.headers.get("retry-after"))
            retryable = response.status in RETRY_STATUSES and (retry_safe or response.status == 429)
            if retryable and attempt < max_retries and (wait is None or wait <= self.max_retry_wait):
                self._sleep(wait if wait is not None else self._backoff(attempt))
                attempt += 1
                continue
            raise self._error(response)

    @staticmethod
    def _error(response: Response) -> Exception:
        payload: Any = None
        try:
            payload = response.json()
        except ValueError:
            payload = response.body.decode("utf-8", "replace")
        detail = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(detail, dict):
            detail = payload if isinstance(payload, dict) else {}
        code = detail.get("code")
        message = detail.get("message") or detail.get("detail") or (payload if isinstance(payload, str) else "") or "error"
        return error_class(response.status)(
            response.status,
            str(code) if code is not None else None,
            str(message),
            request_id=detail.get("request_id") or response.request_id,
            param=detail.get("param"),
            body=payload,
            headers=response.headers,
        )

    # --- pagination -----------------------------------------------------------------------------------------------
    def paginate(
        self,
        op: Operation,
        *,
        path: Optional[Mapping[str, Any]] = None,
        query: Optional[Mapping[str, Any]] = None,
        accept_language: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Any]:
        """Every item of a list operation, page after page (same filters on every page)."""
        if op.page is None:
            raise ValueError(f"{op.id} is not a paginated list")
        param, next_field, items_field, has_more_field = op.page
        params = dict(query or {})
        while True:
            page = self.call(op, path=path, query=params, accept_language=accept_language, options=options) or {}
            yield from page.get(items_field) or []
            token = page.get(next_field)
            if token is None or token == "" or (has_more_field and not page.get(has_more_field)):
                return
            params[param] = token


class Product:
    """One product of the API (``client.studio``, ``client.audits``, ``client.leads``)."""

    def __init__(self, client: Client) -> None:
        self._client = client
