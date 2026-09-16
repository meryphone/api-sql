import logging
from secrets import compare_digest

from fastapi import APIRouter, Depends, FastAPI, File, Header, HTTPException, Response, UploadFile

from app import repository
from app.adapters.sharepoint.client import upload_to_sharepoint
from app.config import settings
from app.exceptions import InvalidFile, EntityNotFound, RepositoryError
from app.schemas import UpdateDocument

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Documents API",
    description="API that connects Copilot Studio and SQL Server to automate the process of comparing versions of vendor documents",
    version="1.0.0",
)

router = APIRouter(prefix="/api")


def verify_token(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Reject the request if the X-API-Key header does not match the token."""
    # Constant-time comparison, so response timing does not reveal the token.
    if not x_api_key or not compare_digest(x_api_key, settings.API_TOKEN):
        logger.warning("Access attempt with an invalid or missing token")
        raise HTTPException(status_code=401, detail="Invalid token")




@router.post("/links/{document_id}", status_code=204, dependencies=[Depends(verify_token)])
def update_document(document_id: str, document: UpdateDocument) -> Response:
    """Update the SharePoint link of a document in the database."""
    try:
        repository.update_document(document_id, document.sharepoint_link)
        return Response(status_code=204)
    except EntityNotFound as e:
        logger.warning("Document %s not found in the database", document_id)
        raise HTTPException(status_code=404, detail=str(e))
    except RepositoryError as e:
        logger.exception("Error updating the link of document %s in the database", document_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sharepoint", status_code=204, dependencies=[Depends(verify_token)])
async def upload_document(file: UploadFile = File(...)) -> Response:
    """Upload the file to SharePoint and start the comparison process."""
    try:
        content = await file.read()
        await upload_to_sharepoint(file.filename, content)
        return Response(status_code=204)
    except InvalidFile as e:
        logger.warning("Rejected document %s: %s", file.filename, e)
        raise HTTPException(status_code=400, detail=f"Error uploading the document: {e}")
    except Exception as e:
        # Graph, auth and network failures raise different types; none of them is the
        # client's fault, so they must not surface as a 400.
        logger.exception("Error uploading document %s to SharePoint", file.filename)
        raise HTTPException(status_code=500, detail=f"Error uploading the document: {e}")


@router.get("/", status_code=200)
def health_check() -> dict:
    """Service health check endpoint."""
    return {"status": "ok"}


app.include_router(router)
