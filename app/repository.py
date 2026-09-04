import logging

import pyodbc

from app.db import get_cursor
from app.exceptions import EntidadNoEncontrada, RepositorioExcepcion

logger = logging.getLogger(__name__)

TABLA_DOCUMENTOS = "documentos"


def actualizar_documento(documento_id: int, sharepoint_link: str) -> None:
    "Utiliza un cursor para actualizar el enlace de SharePoint de un documento en la base de datos."
    try:
        with get_cursor() as cursor:
            cursor.execute(
                f"UPDATE {TABLA_DOCUMENTOS} SET sharepoint_link = ? WHERE id = ?",
                sharepoint_link,
                documento_id,
            )
            if cursor.rowcount == 0:
                logger.warning(
                    "No se pudo actualizar: no existe el documento %s", documento_id
                )
                raise EntidadNoEncontrada(
                    f"La entidad con id {documento_id} no se ha encontrado."
                )
    except pyodbc.Error as e:
        logger.exception("Error al actualizar el documento %s", documento_id)
        raise RepositorioExcepcion(
            f"Error al actualizar el documento con id {documento_id}: {e}"
        ) from e

    logger.info(
        "Documento %s actualizado (sharepoint_link=%s)", documento_id, sharepoint_link
    )
