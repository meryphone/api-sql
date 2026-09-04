import logging
from contextlib import contextmanager

import pyodbc

from app.config import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_cursor():
    """Entrega un cursor con su propia conexion del pool."""
    connection = pyodbc.connect(settings.connection_string)
    try:
        cursor = connection.cursor()
        yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
