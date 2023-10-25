"""
module: plugins
title: 插件
description: 可根据需求开启相应插件
author: emryslou@gmail.com
examples:
    # how to use:
    plugins_config = {
        # 'authentication': {...}, # 关闭该插件
        'database': {...}, # 开启该插件
        # 'exceptions': {...}, # 应用异常处理: 自动开启，且无法关闭
        # 'graphql': {...},
        # 'http': {...},
        # 'lifespan': {...},  # lifespan: 自动开启，且无法关闭
        # 'logging': {...},
        # 'schema': {...},
        # 'template': {...}
    }

    app = Yaa() # 默认开启: exceptions, lifespan
    app = Yaa(plugins={'database': {...}}) # 开启: exceptions, lifespan, database
exposes:
    - plugin_middlewares
    - load_middlewares
plugins:
    - authentication
    - database
    - exceptions
    - graphql
    - http
    - logging
    - schema
    - template
"""
import warnings

from yaa.applications import Yaa


class _plugin_middlewares(object):
    def __init__(self) -> None:
        self.middlewares: dict = {}

    def add(self, key: str, cls: type, options: dict) -> None:
        self.middlewares[key] = (cls, options)

    def clear(self) -> None:
        self.middlewares = {}


plugin_middlewares = _plugin_middlewares()


def load_middlewares(app: Yaa, package: str, middlewares_config: dict = {}) -> dict:
    from yaa._utils import get_plugin_middlewares

    klass: dict = {}
    middlewares = get_plugin_middlewares(package)
    for mw_name, mw_config in middlewares_config.items():
        if mw_name in middlewares:
            plugin_middlewares.add(
                f"{package}.{mw_name}", middlewares[mw_name], mw_config
            )
        else:
            warnings.warn(
                f"middleware {mw_name} not found, and skipped"
            )  # pragma: no cover

    return klass
