import logging
from contextlib import asynccontextmanager
from secrets import compare_digest

from fastapi import APIRouter, Depends, FastAPI, File, Header, HTTPException, Response, UploadFile

from app import repository
from app.adapters.sharepoint.client import cerrar_cliente, iniciar_cliente, subir_sharepoint
from app.config import settings
from app.exceptions import EntidadNoEncontrada, RepositorioExcepcion
from app.schemas import actualizarDocumento

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await iniciar_cliente()
    yield
    await cerrar_cliente()


app = FastAPI(
    title="API de Documentos",
    description="API para la adición de información sobre documentos de vendedores",
    version="1.0.0",
    lifespan=lifespan,
)

router = APIRouter(prefix="/api")


def verificar_token(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Rechaza la petición si la cabecera X-API-Key no coincide con el token."""
    if not x_api_key or not compare_digest(x_api_key, settings.API_TOKEN):
        logger.warning("Intento de acceso con token inválido o ausente")
        raise HTTPException(status_code=401, detail="Token inválido")




@router.post("/links", status_code=204, dependencies=[Depends(verificar_token)])
def actualizar_documento(documento: actualizarDocumento) -> Response:
    """Actualiza el enlace de SharePoint de un documento en la base de datos."""
    try:
        repository.actualizar_documento(documento.id, documento.sharepoint_link)
        return Response(status_code=204)
    except EntidadNoEncontrada as e:
        logger.exception(f"Documento {actualizarDocumento.id} no encontrado en la base de datos")
        raise HTTPException(status_code=404, detail=str(e))
    except RepositorioExcepcion as e:
        logger.exception(f"Error al actualizar el link del documento {actualizarDocumento.id} en la base de datos")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sharepoint", status_code=204, dependencies=[Depends(verificar_token)])
async def subir_documento(comprimido: UploadFile = File(...)) -> Response:
    """Sube el comprimido a SharePoint e inicia el proceso de comparacion."""
    try:
        contenido = await comprimido.read()
        await subir_sharepoint(comprimido.filename, contenido)
        return Response(status_code=204)
    except ValueError as e:
        logger.exception(f"Error al subir el documento {comprimido.filename}: {e}")
        raise HTTPException(status_code=400, detail=f"Error al subir el documento: {e}")
    except Exception as e:
        logger.exception(f"Error al subir el documento {comprimido.filename} a SharePoint")
        raise HTTPException(status_code=500, detail=f"Error al subir el documento: {e}")
    


app.include_router(router)
