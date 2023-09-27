from yast.applications import Yast
# from .middlewares import SessionMiddleware
from yast.plugins import load_middlewares

__name__ = "session"


def plugin_init(app: Yast, config={}) -> None:
    if "middlewares" not in config:
        if "secret_key" not in config:
            config["secret_key"] = "changeme"  # pragma: nocover
        secret_key = config.pop("secret_key")
        config["middlewares"] = {"session": {"secret_key": secret_key}}
    load_middlewares(app, __package__, config["middlewares"])
