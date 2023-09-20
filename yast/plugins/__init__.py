import warnings

from yast.applications import Yast


def load_middlewares(app: Yast, package: str, middlewares_config: dict = {}):
    from yast.utils import get_plugin_middlewares

    middlewares = get_plugin_middlewares(package)
    for mw_name, mw_config in middlewares_config.items():
        if mw_name in middlewares:
            app.add_middleware(middlewares[mw_name], **mw_config)
        else:
            warnings.warn(f"middleware {mw_name} not found, and skipped")

    return middlewares
