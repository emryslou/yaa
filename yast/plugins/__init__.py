import warnings

from yast.applications import Yast


class _plugin_middlewares(object):
    def __init__(self):
        self.middlewares = {}

    def add(self, key, cls, options):
        self.middlewares[key] = (cls, options)


plugin_middlewares = _plugin_middlewares()


def load_middlewares(app: Yast, package: str, middlewares_config: dict = {}):
    from yast.utils import get_plugin_middlewares

    klass = {}
    middlewares = get_plugin_middlewares(package)
    for mw_name, mw_config in middlewares_config.items():
        if mw_name in middlewares:
            plugin_middlewares.add(
                f"{package}.{mw_name}", middlewares[mw_name], mw_config
            )
            # klass[mw_name] = app.add_middleware(middlewares[mw_name], **mw_config)
        else:
            warnings.warn(f"middleware {mw_name} not found, and skipped")

    return klass
