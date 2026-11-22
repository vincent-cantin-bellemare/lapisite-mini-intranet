"""Webhook signatures (handwritten), as the Webhooks guide describes them.

``Lapisite-Webhook-Signature`` holds one or two ``v1=<hex>`` values separated by a comma; each is the HMAC-SHA256 of
``"<timestamp>.<raw body>"`` keyed with the endpoint's secret. One match is enough (two values while a secret
rotates). A timestamp more than 5 minutes away from the clock is refused (replays).

    from lapisite.webhooks import construct_event

    event = construct_event(request.get_data(), request.headers, secret)   # raises WebhookSignatureError
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Mapping, Optional, Union

from .errors import WebhookSignatureError

SIGNATURE_HEADER = "Lapisite-Webhook-Signature"
TIMESTAMP_HEADER = "Lapisite-Webhook-Timestamp"
ID_HEADER = "Lapisite-Webhook-Id"
TOLERANCE_SECONDS = 300

Body = Union[bytes, bytearray, str]


def _bytes(body: Body) -> bytes:
    return body.encode("utf-8") if isinstance(body, str) else bytes(body)


def compute_signature(secret: str, timestamp: Union[int, str], body: Body) -> str:
    """The ``v1`` value Lapisite sends for this body: lowercase hexadecimal HMAC-SHA256."""
    message = str(int(timestamp)).encode("ascii") + b"." + _bytes(body)
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signature(
    body: Body,
    timestamp: Optional[str],
    signature_header: Optional[str],
    secret: str,
    *,
    tolerance: int = TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> None:
    """Raises ``WebhookSignatureError`` unless the signature is valid and fresh. ``body``: the raw bytes received."""
    if not secret:
        raise WebhookSignatureError("no webhook secret given")
    try:
        stamp = int(str(timestamp).strip())
    except (TypeError, ValueError):
        raise WebhookSignatureError(f"missing or unreadable {TIMESTAMP_HEADER}") from None
    clock = time.time() if now is None else now
    if abs(clock - stamp) > tolerance:
        raise WebhookSignatureError(f"timestamp {stamp} is more than {tolerance} s away from now")
    expected = compute_signature(secret, stamp, body).encode("ascii")
    valid = False
    for part in (signature_header or "").split(","):
        scheme, _, value = part.strip().partition("=")
        if scheme == "v1" and hmac.compare_digest(value.strip().encode("ascii", "replace"), expected):
            valid = True
    if not valid:
        raise WebhookSignatureError(f"no {SIGNATURE_HEADER} value matches")


def _header(headers: Mapping[str, str], name: str) -> Optional[str]:
    value = headers.get(name)
    if value is None:
        lowered = name.lower()
        value = next((v for k, v in headers.items() if k.lower() == lowered), None)
    return value


def construct_event(
    body: Body,
    headers: Mapping[str, str],
    secret: str,
    *,
    tolerance: int = TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> Any:
    """Verifies the request (raw body + its headers) and returns the parsed event; deduplicate on ``event['id']``."""
    verify_signature(
        body,
        _header(headers, TIMESTAMP_HEADER),
        _header(headers, SIGNATURE_HEADER),
        secret,
        tolerance=tolerance,
        now=now,
    )
    try:
        return json.loads(_bytes(body).decode("utf-8"))
    except ValueError:
        raise WebhookSignatureError("the signed body is not JSON") from None
