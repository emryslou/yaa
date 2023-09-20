"""
title: DatabaseMiddleware
module: DatabaseMiddleware
description:
    数据库组建，可用于支持各种类型的数据库，需通过 plugin_init 启用
"""
__all__ = [
    "compile",
    "DatabaseBackend",
    "DatabaseSession",
    "DatabaseTransaction",
    "get_database_backend",
]

__name__ = "database"

from yast.applications import Yast
from yast.datastructures import DatabaseURL

from .drivers.base import DatabaseBackend, DatabaseSession, DatabaseTransaction, compile


def plugin_init(app: Yast, config: dict = {}):
    mw_db_config = config.get("middleware", {}).get("database", {})
    if mw_db_config:
        from yast.plugins.database.middlewares import DatabaseMiddleware

        app.add_middleware(DatabaseMiddleware, **mw_db_config)


def get_database_backend(database_url: DatabaseURL, *args, **kwargs) -> DatabaseBackend:
    try:
        import pymysql as _  # noqa

        from .drivers.mysql import MysqlBackend  # noqa
    except ImportError:  # pragma: nocover
        pass  # pragma: nocover

    try:
        import psycopg2 as _  # noqa

        from .drivers.postgres import PostgresBackend  # noqa
    except ImportError:  # pragma: nocover
        pass  # pragma: nocover

    driver = DatabaseBackend.drivers.get(database_url.scheme, None)
    if driver is not None:
        return driver(database_url, *args, **kwargs)

    raise RuntimeError(f"driver `{database_url.scheme}` cannot be supported")
