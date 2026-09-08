"""Cliente de Microsoft Graph para subir documentos a SharePoint."""

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.exceptions import ArchivoInvalido
from app.adapters.sharepoint.auth import obtener_token

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TAMANO_LIMITE_SUBIDA_SIMPLE = 4 * 1024 * 1024
TAMANO_FRAGMENTO_SUBIDA_GRANDE = 10 * 320 * 1024
TAMANO_MAXIMO_ARCHIVO = 512 * 1024 *1024
REINTENTOS = 3
BACKOFF_BASE_SEGUNDOS = 1
CODIGOS_REINTENTABLES = {429, 500, 502, 503, 504}

_cliente = httpx.AsyncClient(timeout=60.0)
_drive_id: str | None = None


def _sitio() -> str:
    """Compone el identificador de sitio que espera Graph."""
    partes = urlparse(settings.SHAREPOINT_URL)
    return f"{partes.netloc}:{partes.path.rstrip('/')}"


async def _headers() -> dict:
    """Devuelve la cabecera de autorización con un token vigente."""
    token = await obtener_token()
    return {"Authorization": f"Bearer {token}"}


async def _resolver_drive_id(cliente: httpx.AsyncClient) -> str:
    """Busca el id del drive de la biblioteca configurada y lo cachea."""
    global _drive_id
    if _drive_id is not None:
        return _drive_id

    url = f"{GRAPH_BASE}/sites/{_sitio()}:/drives"
    respuesta = await _con_reintentos(cliente.get, url, headers=await _headers())
    for drive in respuesta.json()["value"]:
        if drive["name"] == settings.BIBLIOTECA_COMENTARIOS:
            _drive_id = drive["id"]
            return _drive_id

    raise RuntimeError(
        f"No se encontró la biblioteca '{settings.BIBLIOTECA_COMENTARIOS}' en {settings.SHAREPOINT_URL}"
    )


async def _drive_root_url(cliente: httpx.AsyncClient) -> str:
    """Devuelve la URL raíz del drive de la biblioteca configurada."""
    drive_id = await _resolver_drive_id(cliente)
    return f"{GRAPH_BASE}/drives/{drive_id}/root"


async def _con_reintentos(metodo, *args, **kwargs) -> httpx.Response:
    """Reintenta con backoff ante 429/5xx (fallos transitorios de Graph)."""
    respuesta = None
    for intento in range(REINTENTOS):
        respuesta = await metodo(*args, **kwargs)
        if respuesta.status_code not in CODIGOS_REINTENTABLES:
            break
        if intento < REINTENTOS - 1:
            await asyncio.sleep(BACKOFF_BASE_SEGUNDOS * (2 ** intento))
    if respuesta.is_error:
        logger.error("Graph respondió %s en %s: %s", respuesta.status_code, respuesta.request.url, respuesta.text)
    respuesta.raise_for_status()
    return respuesta


async def _subir_pequeno(cliente: httpx.AsyncClient, nombre_archivo: str, contenido: bytes) -> dict:
    """Sube el fichero de una sola vez (hasta 4 MB)."""
    raiz = await _drive_root_url(cliente)
    url = f"{raiz}:/{nombre_archivo}:/content"
    respuesta = await _con_reintentos(cliente.put, url, headers=await _headers(), content=contenido)
    return respuesta.json()


async def _crear_sesion_subida(cliente: httpx.AsyncClient, nombre_archivo: str) -> str:
    """Abre una sesión de subida por rangos y devuelve su URL."""
    raiz = await _drive_root_url(cliente)
    url = f"{raiz}:/{nombre_archivo}:/createUploadSession"
    body = {"item": {"@microsoft.graph.conflictBehavior": "replace"}}
    respuesta = await _con_reintentos(cliente.post, url, headers=await _headers(), json=body)
    return respuesta.json()["uploadUrl"]


async def _subir_grande(cliente: httpx.AsyncClient, nombre_archivo: str, contenido: bytes) -> dict:
    """Sube el fichero por fragmentos usando una sesión de subida."""
    url_subida = await _crear_sesion_subida(cliente, nombre_archivo)
    tamano_total = len(contenido)
    respuesta = None

    for inicio in range(0, tamano_total, TAMANO_FRAGMENTO_SUBIDA_GRANDE):
        fin = min(inicio + TAMANO_FRAGMENTO_SUBIDA_GRANDE, tamano_total)
        fragmento = contenido[inicio:fin]
        headers = {
            "Content-Length": str(len(fragmento)),
            "Content-Range": f"bytes {inicio}-{fin - 1}/{tamano_total}",
        }
        respuesta = await _con_reintentos(cliente.put, url_subida, headers=headers, content=fragmento)

    return respuesta.json()



async def subir_sharepoint(nombre_archivo: str, contenido: bytes) -> str:
    """Sube el fichero comprimido a la ruta configurada e inicia el proceso de comparacion."""

    if not contenido:
        raise ArchivoInvalido(f"El archivo {nombre_archivo} está vacío")

    if len(contenido) > TAMANO_MAXIMO_ARCHIVO:
        raise ArchivoInvalido(f"El tamaño del archivo {nombre_archivo} excede el límite de 512MB")

    if len(contenido) <= TAMANO_LIMITE_SUBIDA_SIMPLE:
        item = await _subir_pequeno(_cliente, nombre_archivo, contenido)
    else:
        item = await _subir_grande(_cliente, nombre_archivo, contenido)

    return item["webUrl"]

