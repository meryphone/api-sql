"""Microsoft Graph client for uploading documents to SharePoint."""

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.exceptions import InvalidFile
from app.adapters.sharepoint.auth import get_token

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SIMPLE_UPLOAD_LIMIT_BYTES = 4 * 1024 * 1024
LARGE_UPLOAD_CHUNK_BYTES = 10 * 320 * 1024
MAX_FILE_SIZE_BYTES = 512 * 1024 * 1024
RETRIES = 3
BACKOFF_BASE_SECONDS = 1
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

_client = httpx.AsyncClient(timeout=60.0)
_drive_id: str | None = None


def _site() -> str:
    """Build the site identifier that Graph expects."""
    parts = urlparse(settings.SHAREPOINT_URL)
    return f"{parts.netloc}:{parts.path.rstrip('/')}"


async def _headers() -> dict:
    """Return the authorization header with a valid token."""
    token = await get_token()
    return {"Authorization": f"Bearer {token}"}


async def _resolve_drive_id(client: httpx.AsyncClient) -> str:
    """Look up the drive id of the configured library and cache it."""
    global _drive_id
    if _drive_id is not None:
        return _drive_id

    url = f"{GRAPH_BASE}/sites/{_site()}:/drives"
    response = await _with_retries(client.get, url, headers=await _headers())
    for drive in response.json()["value"]:
        if drive["name"] == settings.COMMENTS_LIBRARY:
            _drive_id = drive["id"]
            return _drive_id

    raise RuntimeError(
        f"Library '{settings.COMMENTS_LIBRARY}' not found in {settings.SHAREPOINT_URL}"
    )


async def _drive_root_url(client: httpx.AsyncClient) -> str:
    """Return the root URL of the configured library's drive."""
    drive_id = await _resolve_drive_id(client)
    return f"{GRAPH_BASE}/drives/{drive_id}/root"


async def _with_retries(method, *args, **kwargs) -> httpx.Response:
    """Retry with backoff on 429/5xx (transient Graph failures)."""
    response = None
    for attempt in range(RETRIES):
        response = await method(*args, **kwargs)
        if response.status_code not in RETRYABLE_STATUS_CODES:
            break
        if attempt < RETRIES - 1:
            await asyncio.sleep(BACKOFF_BASE_SECONDS * (2 ** attempt))
    if response.is_error:
        logger.error("Graph returned %s at %s: %s", response.status_code, response.request.url, response.text)
    response.raise_for_status()
    return response


async def _upload_small(client: httpx.AsyncClient, filename: str, content: bytes) -> dict:
    """Upload the file in a single request (up to 4 MB)."""
    root = await _drive_root_url(client)
    url = f"{root}:/{filename}:/content"
    response = await _with_retries(client.put, url, headers=await _headers(), content=content)
    return response.json()


async def _create_upload_session(client: httpx.AsyncClient, filename: str) -> str:
    """Open a ranged upload session and return its URL."""
    root = await _drive_root_url(client)
    url = f"{root}:/{filename}:/createUploadSession"
    body = {"item": {"@microsoft.graph.conflictBehavior": "replace"}}
    response = await _with_retries(client.post, url, headers=await _headers(), json=body)
    return response.json()["uploadUrl"]


async def _upload_large(client: httpx.AsyncClient, filename: str, content: bytes) -> dict:
    """Upload the file in chunks using an upload session."""
    upload_url = await _create_upload_session(client, filename)
    total_size = len(content)
    response = None

    for start in range(0, total_size, LARGE_UPLOAD_CHUNK_BYTES):
        end = min(start + LARGE_UPLOAD_CHUNK_BYTES, total_size)
        chunk = content[start:end]
        headers = {
            "Content-Length": str(len(chunk)),
            "Content-Range": f"bytes {start}-{end - 1}/{total_size}",
        }
        response = await _with_retries(client.put, upload_url, headers=headers, content=chunk)

    return response.json()



async def upload_to_sharepoint(filename: str, content: bytes) -> str:
    """Upload the compressed file to the configured path and start the comparison process."""

    if not content:
        raise InvalidFile(f"File {filename} is empty")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise InvalidFile(f"File {filename} exceeds the 512MB limit")

    if len(content) <= SIMPLE_UPLOAD_LIMIT_BYTES:
        item = await _upload_small(_client, filename, content)
    else:
        item = await _upload_large(_client, filename, content)

    return item["webUrl"]
