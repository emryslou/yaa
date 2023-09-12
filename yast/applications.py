import inspect
import typing
from asyncio import iscoroutinefunction

from yast.datastructures import URL, URLPath
from yast.graphql import GraphQLApp
from yast.lifespan import EventType, LifeSpanHandler
from yast.middlewares import (
    BaseHttpMiddleware,
    ExceptionMiddleware,
    ServerErrorMiddleware,
)
from yast.routing import BaseRoute, Route, Router
from yast.types import ASGIApp, ASGIInstance, Scope


class Yast(object):
    def __init__(self, debug: bool = False, template_directory: str = None) -> None:
        self._debug = debug
        self.router = Router(routes=[])
        self.lifespan_handler = LifeSpanHandler()
        self.app = self.router
        self.exception_middleware = ExceptionMiddleware(self.router, debug=debug)
        self.error_middleware = ServerErrorMiddleware(
            self.exception_middleware,
            debug=debug,
        )
        self.schema_generator = None
        self.template_env = self.load_template_env(template_directory)

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

    def on_event(self, event_type: EventType) -> None:
        return self.lifespan_handler.on_event(event_type)

    def add_event_handler(self, event_type: EventType, func: typing.Callable) -> None:
        self.lifespan_handler.add_event_handler(event_type, func)

    @debug.setter
    def debug(self, val: bool) -> None:
        self._debug = val
        self.exception_middleware.debug = val
        self.error_middleware.debug = val

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        self.router.mount(path, app=app, name=name)

    def add_exception_handler(
        self,
        exc_class_or_status_code: typing.Union[int, typing.Type[Exception]],
        handler: typing.Callable,
    ) -> None:
        if exc_class_or_status_code in (500, Exception):
            self.error_middleware.handler = handler
        else:
            self.exception_middleware.add_exception_handler(
                exc_class_or_status_code, handler
            )

    def exception_handler(
        self, exc_class_or_status_code: typing.Union[int, typing.Type[Exception]]
    ) -> typing.Callable:
        def decorator(func):
            self.add_exception_handler(exc_class_or_status_code, func)
            return func

        return decorator

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

    def add_middleware(self, middleware_class: type, **kwargs: typing.Any) -> None:
        self.error_middleware.app = middleware_class(
            self.error_middleware.app, **kwargs
        )

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

    def load_template_env(self, template_directory: str = None) -> typing.Any:
        if template_directory is None:
            return None

        import jinja2

        @jinja2.pass_context
        def url_for(context: dict, name: str, **path_params: typing.Any) -> str:
            req = context["request"]
            return req.url_for(name, **path_params)

        loader = jinja2.FileSystemLoader(str(template_directory))
        env = jinja2.Environment(loader=loader, autoescape=True)
        env.globals["url_for"] = url_for
        return env

    def get_template(self, name: str) -> typing.Any:
        return self.template_env.get_template(name)

    def __call__(self, scope: Scope) -> ASGIInstance:
        scope["app"] = self
        if scope["type"] == "lifespan":
            return self.lifespan_handler(scope)

        return self.error_middleware(scope)
