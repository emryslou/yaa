import enum
import inspect
import re
import typing
from asyncio import iscoroutinefunction

from yast.concurrency import run_in_threadpool
from yast.convertors import CONVERTOR_TYPES, Convertor
from yast.datastructures import URL, Headers, URLPath
from yast.exceptions import HttpException
from yast.requests import Request
from yast.responses import PlainTextResponse, RedirectResponse
from yast.types import ASGIApp, Receive, Scope, Send
from yast.websockets import WebSocket, WebSocketClose


class NoMatchFound(Exception):
    pass


class Match(enum.Enum):
    NONE = 0
    PARTIAL = 1
    FULL = 2


PARAM_REGEX = re.compile("{([a-zA-Z_][a-zA-Z0-9_]*)(:[a-zA-Z_][a-zA-Z0-9_]*)?}")


def compile_path(
    path: str,
) -> typing.Tuple[typing.Pattern, str, typing.Dict[str, Convertor]]:
    path_regex = "^"
    path_format = ""

    idx = 0
    param_converts = {}

    for match in PARAM_REGEX.finditer(path):
        param_name, convert_type = match.groups("str")
        convert_type = convert_type.lstrip(":")
        assert (
            convert_type in CONVERTOR_TYPES
        ), f'Unknown path convertor "{convert_type}"'
        convertor = CONVERTOR_TYPES[convert_type]

        path_regex += path[idx : match.start()]
        path_regex += "(?P<%s>%s)" % (param_name, convertor.regex)

        path_format += path[idx : match.start()]
        path_format += "{%s}" % param_name

        param_converts[param_name] = convertor

        idx = match.end()
    # endfor

    path_regex += path[idx:] + "$"
    path_format += path[idx:]

    return re.compile(path_regex), path_format, param_converts


class BaseRoute(object):
    def matches(self, scope: Scope) -> typing.Tuple[Match, Scope]:
        raise NotImplementedError()  # pragma: nocover

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        raise NotImplementedError()  # pragma: nocover

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        raise NotImplementedError()  # pragma: nocover

    def __str__(self) -> str:
        return "%s(path=%s,endpoint=%s)" % (
            self.__class__.__name__,
            getattr(self, "path", ""),
            getattr(self, "name", ""),
        )


class Route(BaseRoute):
    def __init__(
        self,
        path: str,
        endpoint: typing.Callable,
        *,
        methods: typing.Sequence[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ) -> None:
        assert path.startswith("/"), 'Routed paths must always start "/"'
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name
        self.include_in_schema = include_in_schema
        if inspect.isfunction(endpoint) or inspect.ismethod(endpoint):
            self.app = req_res(endpoint)
            if methods is None:
                methods = ["GET"]
        else:
            self.app = endpoint

        if methods is None:
            self.methods = None
        else:
            self.methods = set([method.upper() for method in methods])
            if "GET" in self.methods:
                self.methods |= set(["HEAD"])

        (self.path_regex, self.path_format, self.param_convertors) = compile_path(path)

    def matches(self, scope: Scope) -> typing.Tuple[Match, Scope]:
        if scope["type"] == "http":
            match = self.path_regex.match(scope["path"])

            if match:
                matched_params = match.groupdict()
                for _k, _v in matched_params.items():
                    matched_params[_k] = self.param_convertors[_k].convert(_v)
                path_params = dict(scope.get("path_params", {}))
                path_params.update(matched_params)
                child_scope = {"endpoint": self.endpoint, "path_params": path_params}
                if self.methods and scope["method"] not in self.methods:
                    return Match.PARTIAL, child_scope
                return Match.FULL, child_scope
        return Match.NONE, {}

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        seen_params = set(path_params.keys())
        excepted_params = set(self.param_convertors.keys())
        if name != self.name or seen_params != excepted_params:
            raise NoMatchFound()
        path, remaining_params = replace_params(
            self.path_format, self.param_convertors, path_params
        )
        return URLPath(protocol="http", path=path)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.methods and scope["method"] not in self.methods:
            if "app" in scope:
                raise HttpException(status_code=405)
            res = PlainTextResponse("Method Not Allowed", 405)
            await res(scope, receive=receive, send=send)
        else:
            await self.app(scope, receive=receive, send=send)

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, Route)
            and self.path == other.path
            and self.endpoint == other.endpoint
            and self.methods == other.methods
        )


class WebSocketRoute(BaseRoute):
    def __init__(
        self, path: str, endpoint: typing.Callable, *, name: str = None
    ) -> None:
        assert path.startswith("/"), 'Routed paths must be always start "/"'
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name

        if inspect.isfunction(endpoint) or inspect.ismethod(endpoint):
            self.app = ws_session(endpoint)
        else:
            self.app = endpoint

        regex = "^" + path + "$"
        regex = re.sub("{([a-zA-Z_][a-zA-Z0-9_]*)}", r"(?P<\1>[^/]+)", regex)

        (self.path_regex, self.path_format, self.param_convertors) = compile_path(path)

    def matches(self, scope: Scope) -> typing.Tuple[Match, Scope]:
        if scope["type"] == "websocket":
            match = self.path_regex.match(scope["path"])
            if match:
                matched_params = match.groupdict()
                for _k, _v in matched_params.items():
                    matched_params[_k] = self.param_convertors[_k].convert(_v)
                path_params = dict(scope.get("path_params", {}))
                path_params.update(matched_params)
                child_scope = {"endpoint": self.endpoint, "path_params": path_params}
                return Match.FULL, child_scope
        return Match.NONE, {}

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        seen_params = set(path_params.keys())
        expected_params = set(self.param_convertors.keys())
        if name != self.name or seen_params != expected_params:
            raise NoMatchFound()
        path, remaining_params = replace_params(
            self.path_format, self.param_convertors, path_params
        )
        assert not remaining_params
        return URLPath(protocol="websocket", path=path)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive=receive, send=send)

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, WebSocketRoute)
            and self.path == other.path
            and self.endpoint == other.endpoint
        )


class Mount(BaseRoute):
    def __init__(
        self,
        path: str,
        app: ASGIApp = None,
        routes: typing.List[BaseRoute] = None,
        name: str = None,
    ) -> None:
        assert path == "" or path.startswith("/"), 'Routed paths must always start "/"'
        assert (
            app is not None or routes is not None
        ), "`app=...` or `routes=[...]` must be specified one of them"
        self.path = path.rstrip("/")
        if routes is None:
            self.app = app
        else:
            self.app = Router(routes=routes)

        self.name = name
        (self.path_regex, self.path_format, self.param_convertors) = compile_path(
            self.path + "/{path:path}"
        )

    @property
    def routes(self):
        return getattr(self.app, "routes", None)

    def matches(self, scope: Scope) -> typing.Tuple[Match, Scope]:
        if scope["type"] in ("http", "websocket"):
            path = scope["path"]
            match = self.path_regex.match(path)
            if match:
                matched_params = match.groupdict()
                for _k, _v in matched_params.items():
                    matched_params[_k] = self.param_convertors[_k].convert(_v)
                remaining_path = "/" + matched_params.pop("path")
                matched_path = path[: -len(remaining_path)]
                path_params = dict(scope.get("path_params", {}))
                path_params.update(matched_params)
                child_scope = {
                    "path_param": path_params,
                    "root_path": scope.get("root_path", "") + matched_path,
                    "path": remaining_path,
                    "endpoint": self.app,
                }
                return Match.FULL, child_scope
        return Match.NONE, {}

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        if self.name is not None and name == self.name and "path" in path_params:
            path_params["path"] = path_params["path"].lstrip("/")
            path, remaining_params = replace_params(
                self.path_format, self.param_convertors, path_params
            )
            if not remaining_params:
                return URLPath(path)

        elif self.name is None or name.startswith(self.name + ":"):
            if self.name is None:
                remaining_name = name
            else:
                remaining_name = name[len(self.name) + 1 :]

            path_params["path"] = ""

            path, remaining_params = replace_params(
                self.path_format, self.param_convertors, path_params
            )
            for route in self.routes or []:
                try:
                    url = route.url_path_for(remaining_name, **remaining_params)
                    return URLPath(
                        protocol=url.protocol, path=path.rstrip("/") + str(url)
                    )
                except NoMatchFound:
                    pass

        raise NoMatchFound()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, Mount)
            and self.path == other.path
            and self.app == other.app
        )


class Host(BaseRoute):
    def __init__(self, host: str, app: ASGIApp, name: str = None) -> None:
        self.host = host
        self.app = app
        self.name = name
        (self.host_regex, self.host_format, self.param_convertors) = compile_path(host)

    @property
    def routes(self) -> typing.List[BaseRoute]:
        return getattr(self.app, "routes", None)

    def matches(self, scope: Scope) -> typing.Tuple[Match, Scope]:
        if scope["type"] in ("http", "websocket"):
            headers = Headers(scope=scope)
            host = headers.get("host", "").split(":")[0]
            matched = self.host_regex.match(host)
            if matched:
                matched_params = matched.groupdict()
                for key, value in matched_params.items():
                    matched_params[key] = self.param_convertors[key].convert(value)
                path_params = dict(scope.get("path_params", {}))
                path_params.update(matched_params)
                child_scope = {"path_params": path_params, "endpoint": self.app}
                return Match.FULL, child_scope
            # endif
        # endif
        return Match.NONE, {}

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        if self.name is not None and name == self.name and "path" in path_params:
            path = path_params.pop("path")
            host, remaining_params = replace_params(
                self.host_format, self.param_convertors, path_params
            )
            if not remaining_params:
                return URLPath(path=path, host=host)
        elif self.name is None or name.startswith(self.name + ":"):
            if self.name is None:
                remaining_name = name
            else:
                remaining_name = name[len(self.name) + 1 :]

            host, remaining_params = replace_params(
                self.host_format, self.param_convertors, path_params
            )

            for route in self.routes or []:
                try:
                    url = route.url_path_for(remaining_name, **remaining_params)
                    return URLPath(path=str(url), protocol=url.protocol, host=host)
                except NoMatchFound:
                    pass
        # endelse
        raise NoMatchFound()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive=receive, send=send)

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, Host)
            and self.host == other.host
            and self.app == other.app
        )


class Router(object):
    def __init__(
        self,
        routes: typing.List[BaseRoute] = None,
        redirect_slashes: bool = True,
        default: ASGIApp = None,
    ) -> None:
        self.routes = [] if routes is None else list(routes)
        self.redirect_slashes = redirect_slashes
        self.default = self.not_found if default is None else default
        self._lifespan = None

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        prefix = Mount(path, app=app, name=name)
        self.routes.append(prefix)

    def host(self, host: str, app: ASGIApp, name: str = None) -> None:
        route = Host(host, app=app, name=name)
        self.routes.append(route)

    def route(
        self,
        path: str,
        methods: typing.Sequence[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_route(
                path,
                func,
                methods=methods,
                name=name,
                include_in_schema=include_in_schema,
            )
            return func

        return decorator

    def route_ws(self, path: str, name: str = None) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_route_ws(path, func, name=name)
            return func

        return decorator

    def add_route(
        self,
        path: str,
        endpoint: typing.Callable,
        methods: typing.Sequence[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ) -> None:
        instance = Route(
            path,
            endpoint=endpoint,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
        )
        self.routes.append(instance)

    def add_route_ws(self, path: str, route: typing.Callable, name: str = None) -> None:
        instance = WebSocketRoute(path, name=name, endpoint=route)
        self.routes.append(instance)

    async def not_found(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await WebSocketClose()(receive, send)
            return

        if "app" in scope:
            raise HttpException(status_code=404)
        await PlainTextResponse("Not Found", 404)(scope, receive, send)

    def url_path_for(self, name: str, **path_params) -> URLPath:
        for route in self.routes:
            try:
                return route.url_path_for(name, **path_params)
            except NoMatchFound:
                pass

        raise NoMatchFound()

    @property
    def lifespan(self):
        return self._lifespan

    @lifespan.setter
    def lifespan(self, lifespan):
        self._lifespan = lifespan

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] in ("http", "websocket", "lifespan")

        if "router" not in scope:
            scope["router"] = self

        partial = None

        for route in self.routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                scope.update(child_scope)
                await route(scope, receive=receive, send=send)
                return
            elif match == Match.PARTIAL and partial is None:
                partial = route
                partial_scope = child_scope

        if partial is not None:
            scope.update(partial_scope)
            await partial(scope, receive=receive, send=send)
            return

        if scope["type"] == "http" and self.redirect_slashes:
            if not scope["path"].endswith("/"):
                redirect_scope = dict(scope)
                redirect_scope["path"] += "/"

                for route in self.routes:
                    match, child_scope = route.matches(redirect_scope)
                    if match != Match.NONE:
                        redirect_url = URL(scope=redirect_scope)
                        res = RedirectResponse(url=str(redirect_url))
                        await res(scope=scope, receive=receive, send=send)
                        return

        if self._lifespan is not None and scope["type"] == "lifespan":
            await self._lifespan(scope, receive=receive, send=send)
            return

        await self.default(scope, receive=receive, send=send)

    def __eq__(self, other: typing.Any) -> bool:
        return isinstance(other, Router) and self.routes == other.routes


class ProtocalRouter(object):
    def __init__(self, protocals: typing.Dict[str, ASGIApp]) -> None:
        self.protocals = protocals

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.protocals[scope["type"]](scope, receive=receive, send=send)


def req_res(func: typing.Callable):
    is_coroutine = iscoroutinefunction(func)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        req = Request(scope, receive)
        if is_coroutine:
            res = await func(req)
        else:
            res = await run_in_threadpool(func, req)

        await res(scope, receive, send)

    return app


def ws_session(func: typing.Callable):
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        session = WebSocket(scope, receive, send)
        await func(session)

    return app


def get_name(endpoint: typing.Callable) -> str:
    if inspect.isfunction(endpoint) or inspect.isclass(endpoint):
        return endpoint.__name__

    return endpoint.__class__.__name__


def replace_params(
    path: str,
    param_converts: typing.Dict[str, Convertor],
    path_params: typing.Dict[str, str],
) -> typing.Tuple[str, dict]:
    for _k, _v in list(path_params.items()):
        if "{" + _k + "}" in path:
            convert = param_converts[_k]
            _v = convert.to_string(_v)
            path = path.replace("{" + _k + "}", _v)
            path_params.pop(_k)
        # end if
    # end for
    return path, path_params
