from yaa.applications import Yaa
from yaa.plugins import load_middlewares

__name__ = "authentication"


def plugin_init(app: Yaa, config: dict = {}):
    load_middlewares(app, __package__, config.pop("middlewares", {}))
