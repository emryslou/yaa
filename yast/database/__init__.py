__all__ = [
    "compile",
    "DatabaseBackend",
    "DatabaseSession",
    "DatabaseTransaction",
    "get_database_backend",
]

from yast.datastructures import URL

from .core import DatabaseBackend, DatabaseSession, DatabaseTransaction, compile
from .postgres import PostgresBackend  # noqa


def get_database_backend(database_url: URL, *args, **kwargs) -> DatabaseBackend:
    driver = DatabaseBackend.drivers.get(database_url.scheme, None)
    if driver is not None:
        return driver(database_url, *args, **kwargs)

    raise RuntimeError(f"driver `{database_url.scheme}` cannot be supported")
