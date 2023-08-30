import typing
import re
from typing import Any

from yast.types import Scope, ASGIApp, ASGIInstance
from yast.response import Response


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
            return Response('Method not allowed', 405, media_type='text/plain')
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
            return Response('Method not allowed', 405, media_type='text/plain')
        return self.app(scope)


class Router(object):
    def __init__(self, routes: typing.List[Route]=[], default: ASGIApp=None) -> None:
        self.routes = routes
        self.default = self.not_found if default is None else default
    

    def __call__(self, scope: Scope) -> ASGIInstance:
        for route in self.routes:
            match, child_scope = route.matches(scope)
            if match:
                return route(child_scope)
        
        return self.not_found(scope)
    
    def not_found(self, scope: Scope) -> ASGIInstance:
        if scope['type'] == 'websocket':
            async def close(receive, send):
                await send({'type': 'websocket.close', 'code': 1001})
            return close
        return Response('Not found', 404, media_type='text/plain')


class ProtocalRouter(object):
    def __init__(self, protocals: typing.Dict[str, ASGIApp]):
        self.protocals = protocals
    
    def __call__(self, scope: Scope) -> ASGIInstance:
        return self.protocals[scope['type']](scope)
