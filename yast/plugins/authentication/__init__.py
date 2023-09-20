from yast.applications import Yast
from yast.plugins import load_middlewares

__name__ = "authentication"


def plugin_init(app: Yast, config: dict = {}):
    load_middlewares(app, __package__, config.pop("middlewares", {}))
