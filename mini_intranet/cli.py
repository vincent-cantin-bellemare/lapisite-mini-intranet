"""Command line: python -m mini_intranet <command>."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional

from . import config, flows


def _say(update: dict) -> None:
    step = f" ({update['step']})" if update.get("step") else ""
    progress = f" {update['progress']}%" if "progress" in update else ""
    print(f"  {update['status']}{progress}{step}", flush=True)


def cmd_create_site(args) -> int:
    created = flows.create_site(config.make_client())
    print(f"site id: {created['site']['id']}")
    print(f"job id:  {created['job']['id']}")
    print(f"next:    python -m mini_intranet follow {created['job']['id']}")
    return 0


def cmd_follow(args) -> int:
    job = flows.follow_job(config.make_client(), args.job_id, timeout=args.timeout, on_update=_say)
    print(f"job {job['id']}: {job['status']}")
    return 0 if job["status"] == "succeeded" else 1


def _publish_and_follow(client, site_id: int, timeout: float) -> int:
    deployment = flows.publish(client, site_id)
    print(f"deployment id: {deployment['id']}")
    deployment = flows.follow_deployment(client, site_id, deployment["id"], timeout=timeout, on_update=_say)
    print(f"deployment {deployment['id']}: {deployment['status']} {deployment.get('url') or ''}".rstrip())
    return 0 if deployment["status"] == "succeeded" else 1


def cmd_publish(args) -> int:
    return _publish_and_follow(config.make_client(), args.site_id, args.timeout)


def cmd_webhook_endpoint(args) -> int:
    from lapisite.errors import PermissionDeniedError

    client = config.make_client()
    try:
        endpoint = client.studio.create_webhook_endpoint(
            body={"url": args.public_url, "description": "mini-intranet sample", "events": [
                "job.succeeded", "job.failed", "deployment.succeeded", "deployment.failed"]},
        )
    except PermissionDeniedError as error:
        if error.code == "sandbox_only":
            print(
                "The API refused: webhook endpoints are not available to test keys (sandbox_only).\n"
                "To try the receiver, run `serve` and use the portal's Simulator (it sends a signed "
                "`webhook.test` event). See the README, section 'Receiving webhooks'.",
                file=sys.stderr,
            )
            return 2
        raise
    print(f"endpoint id: {endpoint['id']}")
    print("Signing secret (shown ONCE, never stored by this tool):")
    print(f"  {endpoint['secret']}")
    print("Put it in your environment now, for example:")
    print("  export LAPISITE_WEBHOOK_SECRET='<the secret above>'")
    return 0


def cmd_serve(args) -> int:
    from . import receiver

    secret = os.environ.get("LAPISITE_WEBHOOK_SECRET", "").strip()
    if not secret:
        print("LAPISITE_WEBHOOK_SECRET is not set (the endpoint's whsec_ secret).", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    receiver.serve(secret, args.port)
    return 0


def cmd_demo(args) -> int:
    client = config.make_client()
    created = flows.create_site(client)
    site_id, job_id = created["site"]["id"], created["job"]["id"]
    print(f"site {site_id}, job {job_id}: following generation")
    job = flows.follow_job(client, job_id, timeout=args.timeout, on_update=_say)
    if job["status"] != "succeeded":
        print(f"generation {job['status']}", file=sys.stderr)
        return 1
    return _publish_and_follow(client, site_id, args.timeout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mini_intranet", description="Sample app for the Lapisite API (test environment).")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, help_):
        p = sub.add_parser(name, help=help_)
        p.set_defaults(func=func)
        return p

    add("create-site", cmd_create_site, "create a fictional site and start its generation")
    p = add("follow", cmd_follow, "follow a generation job until it ends")
    p.add_argument("job_id", type=int)
    p.add_argument("--timeout", type=float, default=300.0)
    p = add("publish", cmd_publish, "publish a site and follow the publication")
    p.add_argument("site_id", type=int)
    p.add_argument("--timeout", type=float, default=300.0)
    p = add("webhook-endpoint", cmd_webhook_endpoint, "register a webhook endpoint (prints the secret once)")
    p.add_argument("public_url")
    p = add("serve", cmd_serve, "run the local webhook receiver")
    p.add_argument("--port", type=int, default=config.DEFAULT_PORT)
    p = add("demo", cmd_demo, "create, follow, publish")
    p.add_argument("--timeout", type=float, default=300.0)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    config.load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except config.ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except flows.FollowTimeout as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except Exception as error:  # an SDK APIError: show the useful fields
        from lapisite.errors import APIError, LapisiteError

        if isinstance(error, APIError):
            print(f"API error {error.status} {error.code}: {error.message} (request {error.request_id})", file=sys.stderr)
            return 1
        if isinstance(error, LapisiteError):
            print(f"error: {error}", file=sys.stderr)
            return 1
        raise
