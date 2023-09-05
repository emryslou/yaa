from asyncio import iscoroutinefunction
import inspect
import typing

from yast.graphql import GraphQLApp
from yast.lifespan import LifeSpanHandler, EventType
from yast.middlewares import ExceptionMiddleware
from yast.routing import Route, Router
from yast.types import ASGIApp, Scope, ASGIInstance

class Yast(object):
    def __init__(self, debug: bool = False) -> None:
        self.router = Router(routes=[])
        self.lifespan_handler = LifeSpanHandler()
        self.app = self.router
        self.exception_middleware = ExceptionMiddleware(
                self.router, debug=debug
            )
    @property
    def debug(self) -> bool:
        return self.exception_middleware.debug
    
    def on_event(self, event_type: EventType) -> None:
        return self.lifespan_handler.on_event(event_type)
    
    def add_event_handler(
            self, event_type: EventType,
            func: typing.Callable
        ) -> None:
        self.lifespan_handler.add_event_handler(event_type, func)

    @debug.setter
    def debug(self, val: bool) -> None:
        self.exception_middleware.debug = val
    
    def mount(
            self, path: str,
            app: ASGIApp, methods:list[str] = None
        ) -> None:
        self.router.mount(path, app=app, methods=methods)
    
    def add_exception_handler(
            self, exc_class: type,
            handler: typing.Callable
        ) -> None:
        self.exception_middleware.add_exception_handler(exc_class, handler)
    
    def exception_handler(self, exc_class: type) -> typing.Callable:
        def decorator(func):
            self.add_exception_handler(exc_class, func)
            return func
        
        return decorator
    
    def add_route(
            self, path: str,
            route: typing.Union[typing.Callable, Route],
            methods: list[str] = None
        ) -> None:    
        self.router.add_route(path, route, methods=methods)
    
    def add_route_ws(
            self, path: str,
            route: typing.Union[typing.Callable, Route]
        ) -> None:
        self.router.add_route_ws(path, route)
    
    def add_route_graphql(
            self, path: str,
            schema: typing.Any,
            executor: typing.Any = None
        ) -> None:
        self.router.add_route_graphql(path, schema=schema)

    def add_middleware(
            self,
            middleware_class: type,
            **kwargs: typing.Any
        ) -> None:
        self.exception_middleware.app = middleware_class(self.app, **kwargs)
    
    def route(self, path: str, methods: list[str] = None) -> typing.Callable:
        def decorator(func):
            self.router.add_route(path, func, methods)
            return func
        
        return decorator
    
    def ws_route(self, path: str) -> typing.Callable:
        def decorator(func):
            self.router.add_route_ws(path, func)
            return func
        
        return decorator

    def __call__(self, scope: Scope) -> ASGIInstance:
        scope['app'] = self
        if scope['type'] == 'lifespan':
            return self.lifespan_handler(scope)
        
        return self.exception_middleware(scope)
