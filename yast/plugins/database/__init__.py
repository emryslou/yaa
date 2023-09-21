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

import importlib
import warnings

from yast.applications import Yast
from yast.datastructures import DatabaseURL
from yast.plugins import load_middlewares

from .drivers.base import DatabaseBackend, DatabaseSession, DatabaseTransaction, compile


def register_db_type(
    db_type: str,
    requires: list[str] = None,
    db_package: str = None,
    package_file: str = None,
):
    try:
        for require_package in requires or []:
            importlib.import_module(require_package)

        if db_package is None:
            db_package = f"{__package__}.drivers"

        if package_file is None:
            importlib.import_module(f"{db_package}.{db_type}")
        else:
            import os
            import sys

            sys.path.append(os.path.dirname(package_file))
            importlib.import_module(db_type)

    except ImportError as exc:
        warnings.warn(f"db `{db_type}` enabled failed, msg: {str(exc)}")


_buildin_db_types = {"mysql": ["pymysql"], "postgres": ["psycopg2"]}


def plugin_init(app: Yast, config: dict = {}):
    for enbale_config in config.get("enable_db_types", []):
        assert "db_type" in enbale_config
        if (
            "requires" not in enbale_config
            and enbale_config["db_type"] in _buildin_db_types
        ):
            enbale_config["requires"] = _buildin_db_types[enbale_config["db_type"]]
        register_db_type(**enbale_config)

    load_middlewares(app, __package__, config.get("middlewares", {}))


def get_database_backend(database_url: DatabaseURL, *args, **kwargs) -> DatabaseBackend:
    driver = DatabaseBackend.drivers.get(database_url.scheme, None)
    if driver is not None:
        return driver(database_url, *args, **kwargs)

    raise RuntimeError(f"driver `{database_url.scheme}` cannot be supported")
