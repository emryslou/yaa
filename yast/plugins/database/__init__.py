__all__ = [
    "compile",
    "DatabaseBackend",
    "DatabaseSession",
    "DatabaseTransaction",
    "get_database_backend",
]

from yast.datastructures import DatabaseURL

from .drivers.base import DatabaseBackend, DatabaseSession, DatabaseTransaction, compile
from .drivers.postgres import PostgresBackend  # noqa


def get_database_backend(database_url: DatabaseURL, *args, **kwargs) -> DatabaseBackend:
    driver = DatabaseBackend.drivers.get(database_url.scheme, None)
    if driver is not None:
        return driver(database_url, *args, **kwargs)

    raise RuntimeError(f"driver `{database_url.scheme}` cannot be supported")
