# lapisite-mini-intranet

A small, readable sample app for the [Lapisite API](https://docs.lapisite.com/docs/en/quickstart), using the
official Python SDK. It runs **only against the test environment** (`lps_test_` keys): nothing it does is real.

It shows how to:

- create a site and follow its generation job (polling with backoff and a timeout);
- publish the site and follow the publication;
- register a webhook endpoint and keep its signing secret out of files;
- receive webhooks and verify their signature with the SDK.

Python 3.11+, standard library only. The SDK is vendored in `vendor/lapisite/` (see `vendor/README.md`).
A French version is in [README.fr.md](README.fr.md).

## Prerequisites

- Python 3.11 or newer.
- A Lapisite agency account with direct API access (opened agency by agency during the pilot) and a **test** key.

## 1. Get a test key

In the agency portal, an owner or admin creates a **test** key on the **API keys** screen (pick the `full` preset).
The key starts with `lps_test_` and is shown **once**. A test key only sees test sites, simulates generation and
publication, and never sends an email. See [Authentication](https://docs.lapisite.com/docs/en/authentication).

## 2. Set up `.env`

```bash
cp .env.example .env
# edit .env: LAPISITE_API_KEY=lps_test_...
```

`.env` is git-ignored. The tool refuses to run when the key does not start with `lps_test_`.

| Variable | Meaning |
| --- | --- |
| `LAPISITE_API_KEY` | Your test key (required) |
| `LAPISITE_API_BASE` | API base URL (default `https://api-test.lapisite.com`) |
| `LAPISITE_WEBHOOK_SECRET` | The webhook endpoint's `whsec_` secret (for `serve`) |

## 3. Commands

```bash
python -m mini_intranet create-site        # creates a fictional site, starts generation, prints site id and job id
python -m mini_intranet follow <job_id>    # polls the job until it ends (--timeout seconds, default 300)
python -m mini_intranet publish <site_id>  # publishes the latest version and follows the publication
python -m mini_intranet demo               # create, follow, publish in one go
```

With a test key, generation is simulated and finishes in seconds. The site uses fictional data
(`boulangerie-exemple.example`).

## 4. Receiving webhooks

Start the receiver (it listens on `127.0.0.1:8787` only):

```bash
export LAPISITE_WEBHOOK_SECRET='whsec_...'   # the endpoint's signing secret
python -m mini_intranet serve                # --port 8787 by default
```

For each request it verifies the `Lapisite-Webhook-Signature` header (HMAC-SHA256 of `"<timestamp>.<raw body>"`,
5-minute tolerance) with `lapisite.webhooks.construct_event`, answers `400` when the signature is wrong or too old,
logs the event type and the site, and answers `204` right away. A repeated event id is ignored.

Lapisite needs a public HTTPS address to reach it. For a quick try, expose the receiver with a tunnel:

```bash
cloudflared tunnel --url http://127.0.0.1:8787
```

Register the public URL it prints:

```bash
python -m mini_intranet webhook-endpoint https://<your-tunnel>.trycloudflare.com
```

The command prints the endpoint's signing secret **once**; put it in `LAPISITE_WEBHOOK_SECRET`. It is never written
to a file.

> **Test keys and webhook endpoints.** Per the [Webhooks guide](https://docs.lapisite.com/docs/en/webhooks),
> creating endpoints through the API needs a live key naming no site; a test key gets `403 sandbox_only`
> (the command explains this and exits with code 2). This sample never uses a live key. To try your receiver
> without one, create the endpoint in the portal (**Webhooks**) and use the portal's **Simulator** ("send a test
> webhook"): it sends a signed `webhook.test` event to your URL.

## 5. Tests

```bash
make test    # no network, no secrets
make lint    # py_compile
```

The tests cover the key guard, the job-follow logic against a fake client, and the receiver (signed body accepted,
tampered or stale body rejected). The test secret is built at runtime.

## Troubleshooting

- `LAPISITE_API_KEY must start with lps_test_`: this sample only runs against the test environment.
- `403 forbidden` on every call: API access is not opened for your agency yet; contact Lapisite.
- `403 sandbox_only`: the operation needs a live key (webhook endpoints, go-live). See above.
- `409 job_already_running`: one job runs per site at a time; follow the current one.
- Webhook answered `400`: wrong secret, a body modified before verification, or a clock more than 5 minutes off.
- The tool times out: raise `--timeout`; the job may still be running, `follow` it again.

## Documentation

- [Quickstart](https://docs.lapisite.com/docs/en/quickstart)
- [SDKs](https://docs.lapisite.com/docs/en/sdk)
- [Authentication](https://docs.lapisite.com/docs/en/authentication)
- [Site lifecycle](https://docs.lapisite.com/docs/en/sites-lifecycle)
- [Webhooks](https://docs.lapisite.com/docs/en/webhooks)

## License

MIT (see `LICENSE`). The vendored SDK in `vendor/lapisite/` is MIT too (see `vendor/LICENSE`).
