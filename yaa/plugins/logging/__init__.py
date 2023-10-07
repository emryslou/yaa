__name__ = "logging"

from yast.applications import Yast
from yast.plugins import load_middlewares


def plugin_init(app: Yast, config: dict = {}) -> None:
    load_middlewares(app, __package__, config.get("middlewares", {}))
