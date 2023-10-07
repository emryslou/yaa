__name__ = "http"


from yaa.applications import Yaa
from yaa.plugins import load_middlewares


def plugin_init(app: Yaa, config: dict = {}) -> None:
    load_middlewares(app, __package__, config.get("middlewares", {}))
