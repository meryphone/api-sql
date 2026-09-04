
from pydantic import BaseModel

class actualizarDocumento(BaseModel):
    id: int
    sharepoint_link: str