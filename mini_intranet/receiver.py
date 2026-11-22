"""A small webhook receiver (standard library only). The SDK verifies the signature."""

from __future__ import annotations

import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Optional, Set

from lapisite.errors import WebhookSignatureError
from lapisite.webhooks import construct_event

log = logging.getLogger("mini_intranet.receiver")
MAX_BODY = 1_000_000  # bytes; an event is a few KB


def make_handler(
    secret: str,
    on_event: Optional[Callable[[dict], None]] = None,
    now: Optional[Callable[[], float]] = None,
):
    """A request handler class bound to one endpoint secret."""
    seen: Set[str] = set()

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status: int) -> None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802 (http.server naming)
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._reply(400)
            if not 0 < length <= MAX_BODY:
                return self._reply(400)
            raw = self.rfile.read(length)  # the raw bytes: never re-serialize before verifying
            try:
                event = construct_event(raw, self.headers, secret, now=now() if now else None)
            except WebhookSignatureError as error:
                log.warning("refused: %s", error)
                return self._reply(400)
            if event.get("id") in seen:  # Lapisite retries: the same event id comes again
                return self._reply(204)
            seen.add(event.get("id"))
            log.info("event %s (site %s)", event.get("type"), event.get("site"))
            if on_event:
                on_event(event)
            self._reply(204)  # answer fast: do the real work elsewhere (a queue)

        def log_message(self, format: str, *args) -> None:  # silence the default access log
            pass

    return Handler


def serve(secret: str, port: int, host: str = "127.0.0.1") -> None:
    server = HTTPServer((host, port), make_handler(secret))
    log.info("listening on http://%s:%d (Ctrl+C to stop)", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
