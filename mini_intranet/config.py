"""Settings from environment variables (and an optional local .env file). Nothing is ever written back."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

DEFAULT_API_BASE = "https://api-test.lapisite.com"
TEST_KEY_PREFIX = "lps_test_"
DEFAULT_PORT = 8787


class ConfigError(Exception):
    """A setting is missing or refused. The message tells the user what to do."""


def load_dotenv(path: Optional[Path] = None, environ: Optional[dict] = None) -> None:
    """Reads KEY=VALUE lines of a .env file into the environment (existing variables win)."""
    env = os.environ if environ is None else environ
    path = path or Path(".env")
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        env.setdefault(name.strip(), value.strip().strip("'\""))


def require_test_key(environ: Optional[Mapping[str, str]] = None) -> str:
    """Returns the API key, or raises ConfigError. This sample only ever runs with a test key."""
    env = os.environ if environ is None else environ
    key = env.get("LAPISITE_API_KEY", "").strip()
    if not key:
        raise ConfigError("LAPISITE_API_KEY is not set. Copy .env.example to .env and put your lps_test_ key in it.")
    if not key.startswith(TEST_KEY_PREFIX):
        raise ConfigError(f"LAPISITE_API_KEY must start with {TEST_KEY_PREFIX}: this sample only runs on the test environment.")
    return key


def api_base(environ: Optional[Mapping[str, str]] = None) -> str:
    env = os.environ if environ is None else environ
    return env.get("LAPISITE_API_BASE", "").strip() or DEFAULT_API_BASE


def make_client(environ: Optional[Mapping[str, str]] = None):
    """The SDK client, after the test-key guard."""
    from lapisite import Lapisite

    return Lapisite(api_key=require_test_key(environ), base_url=api_base(environ))
