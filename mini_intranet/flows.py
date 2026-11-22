"""The Lapisite flows of the sample: create a site, follow a job, publish. `client` is a lapisite.Lapisite."""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, Iterable, Optional

# A fictional site: `.example` domains never resolve.
SAMPLE_SITE = {"domain": "boulangerie-exemple.example", "name": "Boulangerie Exemple"}

JOB_DONE = ("succeeded", "failed", "cancelled")
DEPLOYMENT_DONE = ("succeeded", "failed")


class FollowTimeout(Exception):
    """The job did not finish within the timeout."""


def poll(
    fetch: Callable[[], Dict[str, Any]],
    done: Iterable[str],
    *,
    timeout: float = 300.0,
    first_delay: float = 1.0,
    max_delay: float = 10.0,
    factor: float = 1.5,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Calls fetch() until its `status` is in `done`, waiting longer each time (backoff, capped).

    Raises FollowTimeout when the timeout is over. Returns the last object read.
    """
    done = tuple(done)
    deadline = clock() + timeout
    delay = first_delay
    while True:
        obj = fetch()
        if on_update:
            on_update(obj)
        if obj["status"] in done:
            return obj
        if clock() + delay > deadline:
            raise FollowTimeout(f"still {obj['status']} after {timeout:g} s")
        sleep(delay)
        delay = min(delay * factor, max_delay)


def create_site(client, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Creates the draft site, then starts its generation. Returns {"site": ..., "job": ...}."""
    site = client.studio.create_site(body=body or SAMPLE_SITE, idempotency_key=str(uuid.uuid4()))
    job = client.studio.generate_site(site["id"], idempotency_key=str(uuid.uuid4()))
    return {"site": site, "job": job}


def follow_job(client, job_id: int, **options: Any) -> Dict[str, Any]:
    return poll(lambda: client.studio.get_job(job_id), JOB_DONE, **options)


def publish(client, site_id: int) -> Dict[str, Any]:
    """Starts a publication of the latest version. Returns the deployment (to follow)."""
    return client.studio.publish_site(site_id, idempotency_key=str(uuid.uuid4()))


def follow_deployment(client, site_id: int, deployment_id: int, **options: Any) -> Dict[str, Any]:
    return poll(lambda: client.studio.get_deployment(site_id, deployment_id), DEPLOYMENT_DONE, **options)
