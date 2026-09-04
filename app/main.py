import logging
from secrets import compare_digest

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response

from app import repository
from app.config import settings
from app.exceptions import EntidadNoEncontrada, RepositorioExcepcion
from app.schemas import actualizarDocumento

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Documentos",
    description="API para la adición de información sobre documentos de vendedores",
    version="1.0.0",
)

router = APIRouter(prefix="/api")


def verificar_token(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Rechaza la petición si la cabecera X-API-Key no coincide con el token."""
    if not x_api_key or not compare_digest(x_api_key, settings.api_token):
        logger.warning("Intento de acceso con token inválido o ausente")
        raise HTTPException(status_code=401, detail="Token inválido")



@router.post("/documentos", status_code=204, dependencies=[Depends(verificar_token)])
async def actualizar_documento(documento: actualizarDocumento) -> Response:
    """Actualiza el enlace de SharePoint de un documento en la base de datos."""
    try:
        repository.actualizar_documento(documento.id, documento.sharepoint_link)
        return Response(status_code=204)
    except EntidadNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RepositorioExcepcion as e:
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(router)
