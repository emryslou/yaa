"""授权组件
examples: plugins/test_authentication.py
"""
from yaa.applications import Yaa
from yaa.plugins import load_middlewares

__name__ = "authentication"


def plugin_init(app: Yaa, config: dict = {}) -> None:
    load_middlewares(app, __package__, config.pop("middlewares", {}))
