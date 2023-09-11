import inspect
import typing
from asyncio import iscoroutinefunction

from yast.datastructures import URL, URLPath
from yast.graphql import GraphQLApp
from yast.lifespan import EventType, LifeSpanHandler
from yast.middlewares import BaseHttpMiddleware, ExceptionMiddleware
from yast.routing import BaseRoute, Route, Router
from yast.types import ASGIApp, ASGIInstance, Scope


class Yast(object):
    def __init__(self, debug: bool = False) -> None:
        self.router = Router(routes=[])
        self.lifespan_handler = LifeSpanHandler()
        self.app = self.router
        self.exception_middleware = ExceptionMiddleware(self.router, debug=debug)
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
        return self.exception_middleware.debug

    def on_event(self, event_type: EventType) -> None:
        return self.lifespan_handler.on_event(event_type)

    def add_event_handler(self, event_type: EventType, func: typing.Callable) -> None:
        self.lifespan_handler.add_event_handler(event_type, func)

    @debug.setter
    def debug(self, val: bool) -> None:
        self.exception_middleware.debug = val

    def mount(self, path: str, app: ASGIApp) -> None:
        self.router.mount(path, app=app)

    def add_exception_handler(self, exc_class: type, handler: typing.Callable) -> None:
        self.exception_middleware.add_exception_handler(exc_class, handler)

    def exception_handler(self, exc_class: type) -> typing.Callable:
        def decorator(func):
            self.add_exception_handler(exc_class, func)
            return func

        return decorator

    def add_route(
        self,
        path: str,
        route: typing.Union[typing.Callable, BaseRoute],
        methods: list[str] = None,
        include_in_schema: bool = True,
    ) -> None:
        self.router.add_route(
            path, route, methods=methods, include_in_schema=include_in_schema
        )

    def add_route_ws(
        self, path: str, route: typing.Union[typing.Callable, BaseRoute]
    ) -> None:
        self.router.add_route_ws(path, route)

    def add_middleware(self, middleware_class: type, **kwargs: typing.Any) -> None:
        self.exception_middleware.app = middleware_class(self.app, **kwargs)

    def route(
        self, path: str, methods: list[str] = None, include_in_schema: bool = True
    ) -> typing.Callable:
        def decorator(func):
            self.router.add_route(
                path, func, methods, include_in_schema=include_in_schema
            )
            return func

        return decorator

    def ws_route(self, path: str) -> typing.Callable:
        def decorator(func):
            self.router.add_route_ws(path, func)
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
        if scope["type"] == "lifespan":
            return self.lifespan_handler(scope)

        return self.exception_middleware(scope)
