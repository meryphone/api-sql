"""Obtención de tokens app-only para Microsoft Graph, cacheados hasta su expiración."""

import asyncio
import time
from threading import Lock

import msal

from app.core.settings import settings

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
MARGEN_EXPIRACION_SEGUNDOS = 60

_lock = Lock()
_token_cacheado: str | None = None
_expira_en = 0.0


def _construir_app_msal() -> msal.ConfidentialClientApplication:
    """Construye el cliente MSAL con el certificado configurado."""
    with open(settings.CERT_PATH, "r", encoding="utf-8") as fichero_cert:
        clave_privada = fichero_cert.read()

    return msal.ConfidentialClientApplication(
        client_id=settings.CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{settings.TENANT_ID}",
        client_credential={
            "private_key": clave_privada,
            "thumbprint": settings.CERT_THUMBPRINT,
        },
    )


async def obtener_token() -> str:
    """Devuelve un token de Graph, reutilizando el cacheado si sigue vigente."""
    global _token_cacheado, _expira_en

    def _procesar():
        global _token_cacheado, _expira_en

        with _lock:
            if _token_cacheado and time.monotonic() < _expira_en:
                return _token_cacheado

            app = _construir_app_msal()
            resultado = app.acquire_token_for_client(scopes=GRAPH_SCOPE)

            if "access_token" not in resultado:
                raise RuntimeError(
                    f"No se pudo obtener el token de Graph: {resultado.get('error_description', resultado)}"
                )

            _token_cacheado = resultado["access_token"]
            _expira_en = time.monotonic() + resultado.get("expires_in", 0) - MARGEN_EXPIRACION_SEGUNDOS
            return _token_cacheado

    return await asyncio.to_thread(_procesar)
