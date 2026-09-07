
from fastapi import UploadFile
from pydantic import BaseModel

class actualizarDocumento(BaseModel):
    "Clase que representa la estructura de datos para actualizar un documento."
    id: int
    sharepoint_link: str

