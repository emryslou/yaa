from yast.applications import Yast

from .middlewares import AuthenticationMiddleware


def plugin_init(app: Yast, config: dict = {}):
    app.add_middleware(AuthenticationMiddleware, **config)
