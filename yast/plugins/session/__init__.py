from yast.applications import Yast

from .middlewares import SessionMiddleware


def plugin_init(app: Yast, config={}) -> None:
    if "secret_key" not in config:
        config["secret_key"] = "changeme"  # pragma: nocover
    app.add_middleware(SessionMiddleware, **config)
