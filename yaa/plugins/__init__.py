import warnings

from yaa.applications import Yaa


class _plugin_middlewares(object):
    def __init__(self) -> None:
        self.middlewares: dict = {}

    def add(self, key: str, cls: type, options: dict) -> None:
        self.middlewares[key] = (cls, options)

    def clear(self) -> None:
        self.middlewares = {}


plugin_middlewares = _plugin_middlewares()


def load_middlewares(app: Yaa, package: str, middlewares_config: dict = {}) -> dict:
    from yaa.utils import get_plugin_middlewares

    klass: dict = {}
    middlewares = get_plugin_middlewares(package)
    for mw_name, mw_config in middlewares_config.items():
        if mw_name in middlewares:
            plugin_middlewares.add(
                f"{package}.{mw_name}", middlewares[mw_name], mw_config
            )
        else:
            warnings.warn(
                f"middleware {mw_name} not found, and skipped"
            )  # pragma: no cover

    return klass
