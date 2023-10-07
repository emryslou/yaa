import typing

from yast.datastructures import State, URLPath
from yast.middlewares import BaseHttpMiddleware, Middleware
from yast.routing import BaseRoute, Router
from yast.types import ASGIApp, Receive, Scope, Send


class Yast(object):
    def __init__(
        self,
        debug: bool = False,
        routes: typing.List[BaseRoute] = None,
        middlewares: typing.List[typing.Tuple[Middleware, dict]] = None,
        exception_handlers: typing.Dict[
            typing.Union[int, typing.Type[Exception]], typing.Callable
        ] = None,
        on_startup: typing.List[typing.Callable] = None,
        on_shutdown: typing.List[typing.Callable] = None,
        lifespan: typing.Callable["Yast", typing.AsyncGenerator] = None,
        **kwargs,
    ) -> None:
        self._debug = debug
        self.state = State()
        self.router = Router(routes=routes)
        self.app = self.router
        self.config = {
            "plugins": {
                "exceptions": {
                    "middlewares": {
                        "exception": dict(debug=self.debug),
                        "servererror": dict(debug=self.debug),
                    },
                },
                "lifespan": {
                    "event_handlers": {
                        "startup": [],
                        "shutdown": [],
                    },
                    "context": None,
                },
            },
        }

        assert lifespan is None or (
            on_shutdown is None and on_startup is None
        ), "Use either `lifespan` or `on_startup`/`on_shutdown`, not both"
        if lifespan is not None:
            self.config["plugins"]["lifespan"]["context"] = lifespan
            self.config["plugins"]["lifespan"]["event_handlers"] = {}
        else:
            if on_startup is not None:
                self.config["plugins"]["lifespan"]["event_handlers"][
                    "startup"
                ] += on_startup
            if on_shutdown is not None:
                self.config["plugins"]["lifespan"]["event_handlers"][
                    "shutdown"
                ] += on_shutdown

        self.exception_handlers = (
            {} if exception_handlers is None else dict(exception_handlers)
        )
        self.user_middlewares = [] if middlewares is None else list(middlewares)
        for _k, _cfg in kwargs.pop("plugins", {}).items():
            if _k in self.config["plugins"]:
                self.config["plugins"][_k].update(_cfg)
            else:
                self.config["plugins"][_k] = _cfg
        self.init_plugins(self.config.get("plugins", {}))
        self.build_middleware_stack()

    def init_plugins(self, plugins_config: dict = {}):
        _all_plugins = {}
        import importlib
        import os

        module_name = "yast.plugins"
        module = importlib.import_module(module_name)
        plugin_middlewares = getattr(module, "plugin_middlewares")
        plugin_middlewares.clear()

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

    def build_middleware_stack(self):
        app = self.app
        from yast.plugins import plugin_middlewares as pmw

        key_srv = "yast.plugins.exceptions.servererror"
        key_exc = "yast.plugins.exceptions.exception"
        (srv, srv_options) = pmw.middlewares.get(key_srv)
        (exc, exc_options) = pmw.middlewares.get(key_exc)

        for _type, _handler in (self.exception_handlers or {}).items():
            if _type in (500, Exception):
                srv_options["handler"] = _handler
            else:
                if "handlers" in srv_options:
                    exc_options["handlers"][_type] = _handler
                else:
                    exc_options["handlers"] = {_type: _handler}
        middlewares = (
            [(srv, srv_options)]
            + [
                middleware
                for _k, middleware in pmw.middlewares.items()
                if _k not in (key_srv, key_exc)
            ]
            + self.user_middlewares
            + [(exc, exc_options)]
        )
        for cls, options in reversed(middlewares):
            if "debug" not in options:
                options["debug"] = self.debug
            app = cls(app=app, **options)
        self.middleware_app = app

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
        self.user_middlewares.append((middleware_class_or_func, kwargs))
        self.build_middleware_stack()

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

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self
        await self.middleware_app(scope, receive, send)
