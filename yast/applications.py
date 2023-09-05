from asyncio import iscoroutinefunction
import inspect
import typing

from yast.graphql import GraphQLApp
from yast.lifespan import LifeSpanHandler, EventType
from yast.middlewares import ExceptionMiddleware
from yast.requests import Request
from yast.responses import Response
from yast.routing import Route, Router, Path, PathPrefix
from yast.types import ASGIApp, Scope, ASGIInstance, Send, Receive
from yast.websockets import WebSocket

def req_res(func: typing.Callable):
    is_coroutine = iscoroutinefunction(func)

    def app(scope: Scope) -> ASGIInstance:
        async def awaitable(recv: Receive, send: Send) -> None:
            req = Request(scope, recv)
            kwargs = scope.get('kwargs', {})
            if is_coroutine:
                res = await func(req, **kwargs)
            else:    
                res = func(req, **kwargs)
            
            await res(recv, send)

        return awaitable

    return app

def ws_session(func: typing.Callable):
    def app(scope: Scope) -> ASGIInstance:
        async def awaitable(recv: Receive, send: Send) -> None:
            session = WebSocket(scope, recv, send)
            await func(session, **scope.get('kwargs', {}))

        return awaitable

    return app

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
        prefix = PathPrefix(path, app=app, methods=methods)
        self.router.routes.append(prefix)
    
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
        if not inspect.isclass(route):
            route = req_res(route)
            if methods is None:
                methods = ['GET']
            
        self.router.routes.append(
            Path(path, route, protocol='http', methods=methods)
        )
    
    def add_route_ws(
            self, path: str,
            route: typing.Union[typing.Callable, Route]
        ) -> None:
        if not inspect.isclass(route):
            route = ws_session(route)
        instance = Path(path, route, protocol='websocket')
        self.router.routes.append(instance)
    
    def add_route_graphql(
            self, path: str,
            schema: typing.Any,
            executor: typing.Any = None
        ) -> None:
        self.add_route(
                path,
                GraphQLApp(schema=schema, executor=executor),
                methods=['GET', 'POST']
            )

    def add_middleware(
            self,
            middleware_class: type,
            **kwargs: typing.Any
        ) -> None:
        self.exception_middleware.app = middleware_class(self.app, **kwargs)
    
    def route(self, path: str, methods: list[str] = None) -> typing.Callable:
        def decorator(func):
            self.add_route(path, func, methods)
            return func
        
        return decorator
    
    def ws_route(self, path: str) -> typing.Callable:
        def decorator(func):
            self.add_route_ws(path, func)
            return func
        
        return decorator

    def __call__(self, scope: Scope) -> ASGIInstance:
        if scope['type'] == 'lifespan':
            return self.lifespan_handler(scope)
        scope['app'] = self
        return self.exception_middleware(scope)
