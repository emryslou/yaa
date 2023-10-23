import typing

from yaa._utils import get_logger
from yaa.datastructures import State, URLPath
from yaa.middlewares import BaseHttpMiddleware, Middleware
from yaa.routing import BaseRoute, Router
from yaa.types import ASGI3App, Lifespan, Receive, Scope, Send

logger = get_logger(__name__)


class Yaa(object):
    def __init__(  # type: ignore
        self,
        debug: bool = False,
        routes: typing.Optional[typing.List[BaseRoute]] = None,
        middlewares: typing.Optional[
            typing.List[typing.Tuple[Middleware, dict]]
        ] = None,
        exception_handlers: typing.Optional[
            typing.Dict[typing.Union[int, typing.Type[Exception]], typing.Callable]
        ] = None,
        on_startup: typing.Optional[typing.List[typing.Callable]] = None,
        on_shutdown: typing.Optional[typing.List[typing.Callable]] = None,
        lifespan: typing.Optional[Lifespan] = None,
        **kwargs,
    ) -> None:
        self._debug = debug
        self.state = State()
        self.router = Router(routes=routes)
        self.app = self.router
        self.config: typing.Dict[str, typing.Any]
        self.init_config(
            lifespan=lifespan, on_startup=on_startup, on_shutdown=on_shutdown
        )

        self.exception_handlers = (
            {} if exception_handlers is None else dict(exception_handlers)
        )
        self.user_middlewares = [] if middlewares is None else list(middlewares)
        for _k, _cfg in kwargs.pop("plugins", {}).items():
            if _k in self.config["plugins"]:
                self.config["plugins"][_k].update(_cfg)  # type: ignore
            else:
                self.config["plugins"][_k] = _cfg  # type: ignore
        self.init_plugins(self.config.get("plugins", {}))
        self.build_middleware_stack()

    def init_config(
        self,
        lifespan: typing.Optional[Lifespan] = None,
        on_startup: typing.Optional[list] = None,
        on_shutdown: typing.Optional[list] = None,
    ) -> None:
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
            self.config["plugins"]["lifespan"]["context"] = lifespan  # type: ignore
            self.config["plugins"]["lifespan"]["event_handlers"] = {}  # type: ignore
        else:
            if on_startup is not None:
                self.config["plugins"]["lifespan"]["event_handlers"][  # type: ignore
                    "startup"
                ] += on_startup
            if on_shutdown is not None:
                self.config["plugins"]["lifespan"]["event_handlers"][  # type: ignore
                    "shutdown"
                ] += on_shutdown

    def init_plugins(self, plugins_config: dict = {}) -> None:
        _all_plugins = {}
        import importlib
        import os

        module_name = "yaa.plugins"
        module = importlib.import_module(module_name)
        plugin_middlewares = getattr(module, "plugin_middlewares")
        plugin_middlewares.clear()

        scan_path = os.path.dirname(module.__file__)  # type: ignore
        for file in os.listdir(scan_path):
            package_path = os.path.join(scan_path, file)  # type: ignore
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

    def build_middleware_stack(self) -> None:
        app = self.app
        from yaa.plugins import plugin_middlewares as pmw

        key_srv = "yaa.plugins.exceptions.servererror"
        key_exc = "yaa.plugins.exceptions.exception"
        (srv, srv_options) = pmw.middlewares.get(key_srv)  # type: ignore[misc]
        (exc, exc_options) = pmw.middlewares.get(key_exc)  # type: ignore[misc]

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

    def mount(
        self, path: str, app: ASGI3App, name: typing.Optional[str] = None
    ) -> None:
        assert app != self
        self.router.mount(path, app=app, name=name)

    def host(self, host: str, app: ASGI3App, name: typing.Optional[str] = None) -> None:
        self.router.host(host, app=app, name=name)

    def add_route(
        self,
        path: str,
        route: typing.Union[typing.Callable, BaseRoute],
        methods: typing.Optional[list[str]] = None,
        name: typing.Optional[str] = None,
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
    ) -> None:
        self.user_middlewares.append((middleware_class_or_func, kwargs))  # type: ignore
        self.build_middleware_stack()

    def route(
        self,
        path: str,
        methods: typing.Optional[list[str]] = None,
        name: typing.Optional[str] = None,
        include_in_schema: bool = True,
    ) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.router.add_route(
                path, func, methods, name=name, include_in_schema=include_in_schema
            )
            return func

        return decorator

    def ws_route(self, path: str, name: typing.Optional[str] = None) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.router.add_route_ws(path, func, name=name)
            return func

        return decorator

    def middleware(self, middleware_type: str) -> typing.Callable:
        assert middleware_type == "http", 'Current only middleware("http") is supported'

        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_middleware(BaseHttpMiddleware, dispatch=func)

            return func

        return decorator

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        logger.debug(f"{__name__}::{self.__class__.__name__}::url_path_for {name}")
        return self.router.url_path_for(name=name, **path_params)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # type: ignore
        scope["app"] = self  # type: ignore
        await self.middleware_app(scope, receive, send)
