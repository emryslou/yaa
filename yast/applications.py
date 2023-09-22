import typing

from yast.datastructures import URLPath
from yast.middlewares import BaseHttpMiddleware
from yast.routing import BaseRoute, Router
from yast.types import ASGIApp, Receive, Scope, Send


class Yast(object):
    def __init__(
        self,
        debug: bool = False,
        routes: typing.List[BaseRoute] = None,
        template_directory: str = None,
        config: dict = None,
        **kwargs,
    ) -> None:
        self._debug = debug
        self.router = Router(routes=routes)
        self.app = self.router
        self.middleware_app = self.app
        self._register_fun_attr = {}
        self.config = {
            "plugins": {
                "exceptions": {
                    "middlewares": {
                        "exception": dict(debug=self.debug),
                        "servererror": dict(debug=self.debug),
                    }
                },
                "lifespan": {},
            },
        }
        for _k, _cfg in kwargs.pop("plugins", {}).items():
            if _k in self.config["plugins"]:
                self.config["plugins"][_k].update(_cfg)
            else:
                self.config["plugins"][_k] = _cfg
        self.__init_plugins__(self.config.get("plugins", {}))

    def __init_plugins__(self, plugins_config: dict = {}):
        _all_plugins = {}
        import importlib
        import os

        module_name = "yast.plugins"
        module = importlib.import_module(module_name)
        scan_path = os.path.dirname(module.__file__)
        for file in os.listdir(scan_path):
            package_path = os.path.join(scan_path, file)
            if not os.path.isdir(package_path) or package_path.endswith("__"):
                continue
            sub_module = importlib.import_module(f"{module_name}.{file}")
            if hasattr(sub_module, "plugin_init"):
                plugin_name = sub_module.__name__.replace(module_name, "").lstrip(".")
                _all_plugins[plugin_name] = sub_module.plugin_init

        for plugin_name, plugin_cfg in plugins_config.items():
            if plugin_name in _all_plugins:
                init_fn = _all_plugins[plugin_name]
                init_fn(self, plugin_cfg)

    @property
    def routes(self) -> typing.List[BaseRoute]:
        return self.router.routes

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, val: bool) -> None:
        self._debug = val

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        assert app != self
        self.router.mount(path, app=app, name=name)

    def host(self, host: str, app: ASGIApp, name: str = None) -> None:
        self.router.host(host, app=app, name=name)

    def add_route(
        self,
        path: str,
        route: typing.Union[typing.Callable, BaseRoute],
        methods: list[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ) -> None:
        self.router.add_route(
            path, route, methods=methods, name=name, include_in_schema=include_in_schema
        )

    def add_route_ws(
        self, path: str, route: typing.Union[typing.Callable, BaseRoute]
    ) -> None:
        self.router.add_route_ws(path, route)

    def add_middleware(
        self,
        middleware_class_or_func: typing.Union[type, typing.Callable],
        **kwargs: typing.Any,
    ):
        self.middleware_app = middleware_class_or_func(self.middleware_app, **kwargs)
        return self.middleware_app

    def route(
        self,
        path: str,
        methods: list[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ) -> typing.Callable:
        def decorator(func):
            self.router.add_route(
                path, func, methods, name=name, include_in_schema=include_in_schema
            )
            return func

        return decorator

    def ws_route(self, path: str, name: str = None) -> typing.Callable:
        def decorator(func):
            self.router.add_route_ws(path, func, name=name)
            return func

        return decorator

    def middleware(self, middleware_type: str) -> typing.Callable:
        assert middleware_type == "http", 'Current only middleware("http") is supported'

        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_middleware(BaseHttpMiddleware, dispatch=func)

            return func

        return decorator

    def url_path_for(self, name, **path_params: str) -> URLPath:
        return self.router.url_path_for(name=name, **path_params)

    def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self
        return self.middleware_app(scope, receive, send)
