from yast.applications import Yast

from .middlewares import AuthenticationMiddleware

__name__ = "authentication"


def plugin_init(app: Yast, config: dict = {}):
    mw_cfg = config.pop("middleware", None)
    if mw_cfg is not None:
        app.add_middleware(AuthenticationMiddleware, **mw_cfg)
