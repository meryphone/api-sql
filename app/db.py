from contextlib import contextmanager

import pyodbc

from app.config import settings


@contextmanager
def get_cursor():
    """Yield a cursor backed by its own connection from the pool.

    Commits when the block finishes and rolls back if it raises.
    """
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
