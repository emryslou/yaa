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


class NoMatchFound(Exception):
    pass

class BaseRoute(object):
    def matches(self, scope: Scope) -> typing.Tuple[bool, Scope]:
        raise NotImplementedError()
    
    def url_for(self, name:str, **path_params: str) -> str:
        raise NotImplementedError()
    
    def __call__(self, scope: Scope) -> ASGIInstance:
        raise NotImplementedError()


class Route(BaseRoute):
    def __init__(
            self, path: str, *, 
            endpoint: typing.Callable,
            methods: typing.Sequence[str] = None
        ) -> None:
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint)
        if inspect.isfunction(endpoint):
            self.app = req_res(endpoint)
        else:
            self.app = endpoint

        regex = '^' + path + '$'
        regex = re.sub('{([a-zA-Z_][a-zA-Z0-9_]*)}', r"(?P<\1>[^/]+)", regex)
        self.path_regex = re.compile(regex)
        self.param_names = set(self.path_regex.groupindex.keys())

    def matches(self, scope: Scope) -> typing.Tuple[bool, Scope]:
        if scope['type'] == 'http':
            match = self.path_regex.match(scope['path'])
            if match:
                path_params = dict(scope.get('path_params', {}))
                path_params.update(match.groupdict())
                child_scope = dict(scope)
                child_scope['path_params'] = path_params
                return True, child_scope
        return False, {}
    
    def url_for(self, name: str, **path_params: str) -> str:
        if name != self.name or self.param_names != set(path_params.keys()):
            raise NoMatchFound()
        
        return replace_params(self.path, **path_params)

    def __call__(self, scope: Scope) -> ASGIInstance:
        if self.methods and scope['method'] not in self.methods:
            if 'app' in scope:
                raise HttpException(status_code=405)
            return PlainTextResponse('Method Not Allowed', 405)
        
        return self.app(scope)
    
    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, Route)
            and self.path == other.path
            and self.endpoint == other.endpoint
            and self.methods == other.methods
        )


class WebSocketRoute(BaseRoute):
    def __init__(
            self, path: str, *,
            endpoint: typing.Callable
        ) -> None:
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint)

        if inspect.isfunction(endpoint):
            self.app = ws_session(endpoint)
        else:
            self.app = endpoint
        
        regex = '^' + path + '$'
        regex = re.sub('{([a-zA-Z_][a-zA-Z0-9_]*)}', r"(?P<\1>[^/]+)", regex)
        self.path_regex = re.compile(regex)
        self.param_names = set(self.path_regex.groupindex.keys())
    
    def matches(self, scope: Scope) -> typing.Tuple[bool, Scope]:
        if scope['type'] == 'websocket':
            match = self.path_regex.match(scope['path'])
            if match:
                path_params = dict(scope.get('path_params', {}))
                path_params.update(match.groupdict())
                child_scope = dict(scope)
                child_scope['path_params'] = path_params
                return True, child_scope
        return False, {}
    
    def url_for(self, name: str, **path_params: str) -> str:
        if name != self.name or self.param_names != set(path_params.keys()):
            raise NoMatchFound()
        
        return replace_params(self.path, **path_params)
    
    def __call__(self, scope: Scope) -> ASGIInstance:
        return self.app(scope)

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, WebSocketRoute)
            and self.path == other.path
            and self.endpoint == other.endpoint
        )


class Mount(BaseRoute):

    def __init__(
            self, path: str,
            app: ASGIApp
        ) -> None:
        self.path = path
        self.app = app

        regex = '^' + path
        regex = re.sub('{([a-zA-Z_][a-zA-Z0-9_]*)}', r"(?P<\1>[^/]+)", regex)
        self.path_regex = re.compile(regex)
        self.param_names = set(self.path_regex.groupindex.keys())

    @property
    def routes(self):
        return getattr(self.app, 'routes', None)
    

    def matches(self, scope: Scope) -> typing.Tuple[bool, Scope]:
        if scope['type'] == 'http':
            match = self.path_regex.match(scope['path'])
            if match:
                path_params = dict(scope.get('path_params', {}))
                path_params.update(match.groupdict())
                child_scope = dict(scope)
                child_scope['root_path'] = scope.get('root_path', '') + match.string
                child_scope['path'] = scope['path'][match.span()[1]:]
                child_scope['path_params'] = path_params
                return True, child_scope
        return False, {}
    
    def url_for(self, name: str, **path_params: str) -> str:
        for route in self.routes or []:
            try:
                return self.path + route.url_for(name, **path_params)
            except NoMatchFound as exc:
                pass

        raise NoMatchFound()

    def __call__(self, scope: Scope) -> ASGIInstance:
        return self.app(scope)
    
    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, Mount)
            and self.path == other.path
            and self.app == other.app
        )


class Router(object):
    def __init__(
            self, routes: typing.List[BaseRoute]=None,
            default: ASGIApp=None
        ) -> None:
        self.routes = [] if routes is None else routes
        self.default = self.not_found if default is None else default
        self.executor = ThreadPoolExecutor()

    def mount(self, path: str, app: ASGIApp) -> None:
        prefix = Mount(path, app=app)
        self.routes.append(prefix)
    
    def add_route(
            self, path: str, endpoint: typing.Callable, 
            methods: typing.Sequence[str] = None
        ) -> None:
        instance = Route(path, endpoint=endpoint, methods=methods)
        self.routes.append(instance)
    
    def add_route_graphql(
            self, path: str, schema: typing.Any, 
            executor: typing.Any = None
        ) -> None:
        route = GraphQLApp(schema=schema, executor=executor)
        self.add_route(path=path, route=route)
    
    def add_route_ws(self, path, route: typing.Callable) -> None:
        instance = WebSocketRoute(path, endpoint=route)
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

def get_name(endpoint: typing.Callable) -> str:
    if inspect.isfunction(endpoint) or inspect.isclass(endpoint):
        return endpoint.__name__
    
    return endpoint.__class__.__name__

def replace_params(path: str, **path_params: str) -> str:
    for _k, _v in path_params.items():
        path = path.replace('{' + _k + '}', _v)
    return path