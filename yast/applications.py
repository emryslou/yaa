import typing

from yast.datastructures import URLPath
from yast.middlewares import BaseHttpMiddleware
from yast.routing import BaseRoute, Router
from yast.types import ASGIApp, ASGIInstance, Scope


class Yast(object):
    def __init__(
        self,
        debug: bool = False,
        template_directory: str = None,
        config: dict = None,
        **kwargs,
    ) -> None:
        self._debug = debug
        self.router = Router(routes=[])
        self.app = self.router
        self.middleware_app = self.app
        self.config = {
            "template_directory": template_directory,
            "plugins": {
                "exceptions": {},
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
        from yast.plugins import (
            exceptions as plugin_exceptions,
            lifespan as plugin_lifespan,
            session as plugin_session,
            template as plugin_template,
        )

        for plugin_name, plugin_cfg in plugins_config.items():
            if plugin_name == "exceptions":
                plugin_exceptions.plugin_init(self, plugin_cfg)
            elif plugin_name == "lifespan":
                plugin_lifespan.plugin_init(self, plugin_cfg)
            elif plugin_name == "session":
                plugin_session.plugin_init(self, plugin_cfg)
            elif plugin_name == "template":
                plugin_template.plugin_init(self, plugin_cfg)

        self.schema_generator = None

    @property
    def routes(self) -> typing.List[BaseRoute]:
        return self.router.routes

    @property
    def schema(self) -> dict:
        assert self.schema_generator is not None
        return self.schema_generator.get_schema(self.routes)

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, val: bool) -> None:
        self._debug = val
        self.exception_middleware.debug = val
        self.error_middleware.debug = val

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        self.router.mount(path, app=app, name=name)

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
    ) -> None:
        self.middleware_app = middleware_class_or_func(self.middleware_app, **kwargs)

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

    def __call__(self, scope: Scope) -> ASGIInstance:
        scope["app"] = self
        return self.middleware_app(scope)
