"""HTTP plumbing for OpenRouter, including networks that inspect TLS (e.g. Zscaler)."""

import logging
import ssl
import threading

import httpx
import truststore

log = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1"
KEEPALIVE_SECONDS = 90.0


def make_http_client() -> httpx.Client:
    """Verifies TLS against the Windows certificate store rather than certifi, so a
    corporate root CA that IT installed on the machine is trusted with no export step.
    Proxies come from HTTPS_PROXY or the static Windows proxy setting (httpx default)."""
    return httpx.Client(
        verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        headers={"X-Title": "My Secretary"},
        # httpx drops idle connections after 5 s by default, shorter than a long
        # Utterance, which would throw away the connection warm_up() just opened.
        limits=httpx.Limits(keepalive_expiry=KEEPALIVE_SECONDS),
    )


def warm_up(client: httpx.Client, api_key: str) -> None:
    """Makes sure a live pooled connection to OpenRouter exists, in the background, so the
    upload at release time does not pay for connection setup. Behind TLS inspection, a cold upload
    was measured at ~2-5 s slower than a warm one. Failures are ignored."""

    def ping():
        try:
            client.get(f"{OPENROUTER_URL}/key", headers={"Authorization": f"Bearer {api_key}"}, timeout=3.0)
        except httpx.HTTPError:
            pass

    threading.Thread(target=ping, daemon=True, name="warm-up").start()


def transport_error_kind(error: httpx.TransportError) -> str:
    """'tls' when the certificate chain is not trusted, otherwise 'network'."""
    cause: BaseException | None = error
    while cause is not None:
        if isinstance(cause, ssl.SSLCertVerificationError):
            return "tls"
        cause = cause.__cause__ or cause.__context__
    return "network"


def check_connection(client: httpx.Client, api_key: str) -> str | None:
    """Setup check: can we reach OpenRouter, and does it accept the key?
    Returns None when all is well, otherwise an error kind for the tray."""
    try:
        response = client.get(
            f"{OPENROUTER_URL}/key",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
    except httpx.TransportError as error:
        kind = transport_error_kind(error)
        log.warning("connection check failed: %s (%s)", kind, type(error).__name__)
        return kind
    if response.status_code in (401, 403):
        return "auth"
    if response.status_code != 200:
        log.warning("connection check failed: HTTP %s", response.status_code)
        return "server"
    log.info("connection check ok")
    return None
