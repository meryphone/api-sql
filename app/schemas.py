
from fastapi import UploadFile
from pydantic import BaseModel


class UpdateDocument(BaseModel):
    "Data structure used to update an evaluation document in the database."
    sharepoint_link: str
