import logging

import pyodbc

from app.db import get_cursor
from app.exceptions import EntityNotFound, RepositoryError

logger = logging.getLogger(__name__)

DOCUMENTS_TABLE = "documentos"


def update_document(document_id: str, sharepoint_link: str) -> None:
    """Use a cursor to update the SharePoint link of a document in the database."""
    try:
        with get_cursor() as cursor:
            # Table names cannot be bound as parameters; DOCUMENTS_TABLE is a constant,
            # never user input. Every value goes through a "?" placeholder.
            cursor.execute(
                f"UPDATE {DOCUMENTS_TABLE} SET sharepoint_link = ? WHERE id = ?",
                sharepoint_link,
                document_id,
            )
            if cursor.rowcount == 0:
                raise EntityNotFound(
                    f"The entity with id {document_id} was not found."
                )
    except pyodbc.Error as e:
        raise RepositoryError(
            f"Error updating the document with id {document_id}: {e}"
        ) from e

    logger.info("Document %s updated", document_id)
    logger.debug("Document %s sharepoint_link=%s", document_id, sharepoint_link)
