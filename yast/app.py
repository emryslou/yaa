from asyncio import iscoroutinefunction
from yast.request import Request
from yast.response import Response
from yast.routing import Router, Path, PathPrefix
from yast.types import ASGIApp, Scope, ASGIInstance, Send, Recevie
from yast.websockets import WebSocketSession

def req_res(func):
    is_coroutine = iscoroutinefunction(func)

    def app(scope: Scope) -> ASGIInstance:
        async def awaitable(recv: Recevie, send: Send) -> None:
            req = Request(scope, recv)
            kwargs = scope.get('kwargs', {})
            if is_coroutine:
                res = await func(req, **kwargs)
            else:    
                res = func(req, **kwargs)
            
            await res(recv, send)

        return awaitable

    return app

def ws_session(func):
    def app(scope: Scope) -> ASGIInstance:
        async def awaitable(recv: Recevie, send: Send) -> None:
            session = WebSocketSession(scope, recv, send)
            await func(session, **scope.get('kwargs', {}))

        return awaitable

    return app

class App(object):
    def __init__(self) -> None:
        self.router = Router(routes=[])
    
    def mount(self, path: str, app: ASGIApp):
        prefix = PathPrefix(path, app=app)
        self.router.routes.append(prefix)
    
    def add_route(self, path: str, route, methods: list[str] = None):
        if methods is None:
            methods = ['GET']
        
        route = Path(path, req_res(route), protocol='http', methods=methods)
        self.router.routes.append(route)
    
    def add_route_ws(self, path: str, route):
        router = Path(path, ws_session(route), protocol='websocket')
        self.router.routes.append(router)
    
    def route(self, path: str, methods: list[str] = None):
        def decorator(func):
            self.add_route(path, func, methods)
        
        return decorator
    
    def ws_route(self, path: str):
        def decorator(func):
            self.add_route_ws(path, func)
        
        return decorator

    def __call__(self, scope: Scope) -> ASGIInstance:
        return self.router(scope)
