# Vendored Lapisite SDK

`lapisite/` is an unmodified copy of the official Lapisite Python SDK, version 0.1.0 (`sdk/VERSION`).
It is copied here so this sample does not depend on any other repository.

**License.** The vendored SDK is released under the MIT license (`vendor/LICENSE`, metadata in `vendor/pyproject.toml`),
like this repository.

**Refresh.** Download the wheel from the docs (https://docs.lapisite.com/docs/en/sdk, "Download"), unzip it
(a wheel is a zip file) and replace `vendor/lapisite/` with the `lapisite/` folder it contains, then run `make test`.
