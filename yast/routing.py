from asyncio import iscoroutinefunction
from concurrent.futures import ThreadPoolExecutor
import inspect
import re
import typing


from yast.exceptions import HttpException
from yast.graphql import GraphQLApp
from yast.requests import Request
from yast.responses import Response, PlainTextResponse
from yast.types import Scope, ASGIApp, ASGIInstance, Receive, Send
from yast.websockets import WebSocketClose, WebSocket



class Route(object):
    def matches(self, scope: Scope) -> typing.Tuple[bool, Scope]:
        raise NotImplementedError() # pragma: no cover
    
    def __call__(self, scope: Scope) -> ASGIInstance:
        raise NotImplementedError() # pragma: no cover


class Path(Route):
    def __init__(
        self,
        path: str,
        app: ASGIApp,
        methods: typing.Sequence[str] = (),
        protocol: str = None
    ) -> None:
        self.path = path
        self.app = app
        self.methods = methods
        self.protocol = protocol

        regex = '^' + path + '$'
        regex = re.sub('{([a-zA-Z_][a-zA-Z0-9_]*)}', r"(?P<\1>[^/]+)", regex)

        self.path_regex = re.compile(regex)
    
    def matches(self, scope: Scope) -> typing.Tuple[bool, Scope]:
        if self.protocol is None or scope['type'] == self.protocol:
            match = self.path_regex.match(scope['path'])
            if match:
                kwargs = dict(scope.get('kwargs', {}))
                kwargs.update(match.groupdict())
                child_scope = dict(scope)
                child_scope['kwargs'] = kwargs
                return True, child_scope
        return False, {}
    
    def __call__(self, scope: Scope) -> ASGIInstance:
        if self.methods and scope['method'] not in self.methods:
            if 'app' in scope:
                raise HttpException(status_code=405)
            return PlainTextResponse('Method Not Allowed', 405)
        return self.app(scope)

class PathPrefix(Route):
    def __init__(
        self,
        path: str,
        app: ASGIApp,
        methods: typing.Sequence[str] = ()
    ) -> None:
        self.path = path
        self.app = app
        self.methods = methods

        regex = '^' + path
        regex = re.sub('{([a-zA-Z_][a-zA-Z0-9_]*)}', r"(?P<\1>[^/]+)", regex)

        self.path_regex = re.compile(regex)
    
    def matches(self, scope: Scope) -> typing.Tuple[bool, Scope]:
        match = self.path_regex.match(scope['path'])
        if match:
            kwargs = dict(scope.get('kwargs', {}))
            kwargs.update(match.groupdict())
            child_scope = dict(scope)
            child_scope['kwargs'] = kwargs
            child_scope['root_path'] = scope.get('root_path', '') + match.string
            child_scope['path'] = scope.get('path', '')[match.span()[1]:]
            return True, child_scope
        return False, {}
    
    def __call__(self, scope: Scope) -> ASGIInstance:
        if self.methods and scope['method'] not in self.methods:
            if 'app' in scope:
                raise HttpException(status_code=405)
            return PlainTextResponse('Method Not Allowed', 405)
        return self.app(scope)


class Router(object):
    def __init__(
            self, routes: typing.List[Route]=[],
            default: ASGIApp=None
        ) -> None:
        self.routes = [] if routes is None else routes
        self.default = self.not_found if default is None else default
        self.executor = ThreadPoolExecutor()

    def mount(
            self, path: str, app: ASGIApp,
            methods: typing.Sequence[str]
        ) -> None:
        prefix = PathPrefix(path, app=app, methods=methods)
        self.routes.append(prefix)
    
    def add_route(
            self, path: str, route: typing.Callable, 
            methods: typing.Sequence[str] = None
        ) -> None:
        if not inspect.isclass(route):
            route = req_res(route)
            methods = ('GET',) if methods is None else methods
        instance = Path(path, route, protocol='http', methods=methods)
        self.routes.append(instance)
    
    def add_route_graphql(
            self, path: str, schema: typing.Any, 
            executor: typing.Any = None
        ) -> None:
        route = GraphQLApp(schema=schema, executor=executor)
        self.add_route(path=path, route=route, methods=['GET', 'POST'])
    
    def add_route_ws(self, path, route: typing.Callable) -> None:
        if not inspect.isclass(route):
            route = ws_session(route)
        instance = Path(path, route, protocol='websocket')
        self.routes.append(instance)

    def __call__(self, scope: Scope) -> ASGIInstance:
        assert scope['type'] in ('http', 'websocket')
        for route in self.routes:
            match, child_scope = route.matches(scope)
            if match:
                return route(child_scope)
        
        return self.not_found(scope)
    
    def not_found(self, scope: Scope) -> ASGIInstance:
        if scope['type'] == 'websocket':
            return WebSocketClose()
        
        if 'app' in scope:
            raise HttpException(status_code=404)
        return PlainTextResponse('Not Found', 404)


class ProtocalRouter(object):
    def __init__(self, protocals: typing.Dict[str, ASGIApp]) -> None:
        self.protocals = protocals
    
    def __call__(self, scope: Scope) -> ASGIInstance:
        return self.protocals[scope['type']](scope)


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
