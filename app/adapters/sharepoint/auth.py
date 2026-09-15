"""App-only token retrieval for Microsoft Graph, cached until expiration."""

import asyncio
import logging
import time
from threading import Lock

import msal

from app.config import settings

logger = logging.getLogger(__name__)

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
EXPIRATION_MARGIN_SECONDS = 60

_lock = Lock()
_cached_token: str | None = None
_expires_at = 0.0


def _build_msal_app() -> msal.ConfidentialClientApplication:
    """Build the MSAL client with the configured certificate."""
    with open(settings.CERT_PATH, "r", encoding="utf-8") as cert_file:
        private_key = cert_file.read()

    return msal.ConfidentialClientApplication(
        client_id=settings.CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{settings.TENANT_ID}",
        client_credential={
            "private_key": private_key,
            "thumbprint": settings.CERT_THUMBPRINT,
        },
    )


async def get_token() -> str:
    """Return a Graph token, reusing the cached one while it is still valid."""
    global _cached_token, _expires_at

    def _acquire():
        global _cached_token, _expires_at

        with _lock:
            if _cached_token and time.monotonic() < _expires_at:
                return _cached_token

            app = _build_msal_app()
            result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)

            if "access_token" not in result:
                raise RuntimeError(
                    f"Could not obtain the Graph token: {result.get('error_description', result)}"
                )

            _cached_token = result["access_token"]
            _expires_at = time.monotonic() + result.get("expires_in", 0) - EXPIRATION_MARGIN_SECONDS
            logger.debug("Acquired new Graph token (expires in %ss)", result.get("expires_in"))
            return _cached_token

    return await asyncio.to_thread(_acquire)
