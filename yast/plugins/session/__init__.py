from yast.applications import Yast

from .middlewares import SessionMiddleware


def plugin_init(app: Yast, config={}) -> None:
    secret_key = config.get("secret_key", "changeme")
    app.add_middleware(SessionMiddleware, secret_key=secret_key)
