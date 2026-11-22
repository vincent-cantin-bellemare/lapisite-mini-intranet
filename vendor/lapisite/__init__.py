"""Official Python SDK of the Lapisite API (``/v1``: Studio, Audits, Leads).

    from lapisite import Lapisite

    client = Lapisite()                      # the key from LAPISITE_API_KEY
    site = client.studio.create_site(body={"domain": "plomberie-exemple.example", "name": "Plomberie Exemple"})
    for site in client.studio.iter_list_sites():
        print(site["id"], site["name"])

The operations (``_operations.py``), the types (``types.py``) and ``_version.py`` are generated from the contract by
``make sdk``; the rest is handwritten. Nothing is published on PyPI before 1.0.0: install the wheel from the docs.
"""

from ._core import Client, Operation, RequestOptions, Response
from ._operations import Audits, Leads, Studio
from ._version import CONTRACT_VERSIONS, __version__
from .errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    GoneError,
    InternalServerError,
    LapisiteError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
    WebhookSignatureError,
)


class Lapisite(Client):
    """The client: ``client.studio``, ``client.audits``, ``client.leads``. See ``Client`` for the options."""

    def __init__(self, api_key=None, **options):  # type: ignore[no-untyped-def]
        super().__init__(api_key, **options)
        self.studio = Studio(self)
        self.audits = Audits(self)
        self.leads = Leads(self)


__all__ = [
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AuthenticationError",
    "BadRequestError",
    "CONTRACT_VERSIONS",
    "Client",
    "ConflictError",
    "GoneError",
    "InternalServerError",
    "Lapisite",
    "LapisiteError",
    "NotFoundError",
    "Operation",
    "PermissionDeniedError",
    "RateLimitError",
    "RequestOptions",
    "Response",
    "UnprocessableEntityError",
    "WebhookSignatureError",
    "__version__",
]
