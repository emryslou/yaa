"""
module: Routing
title: 路由控制模块
description:
    路由相关控制模块
author: emryslou@gmail.com
examples: @(file):test_routing.py
exposes:
    - BaseRoute
    - Route
    - WebSocketRoute
    - Mount
    - Host
    - Router
"""
import enum
import functools
import inspect
import re
import typing

from yaa.concurrency import run_in_threadpool
from yaa.convertors import CONVERTOR_TYPES, Convertor
from yaa.datastructures import URL, Headers, URLPath
from yaa.exceptions import HttpException
from yaa.middlewares import Middleware
from yaa.requests import Request
from yaa.responses import PlainTextResponse, RedirectResponse
from yaa.types import ASGI3App, ASGIApp, P, Receive, Scope, Send
from yaa.websockets import WebSocket, WebSocketClose


class NoMatchFound(Exception):
    """
    由 `.url_path_for(name, **path_params)` 抛出的异常
    原因: 没有匹配到 `route`
    """

    def __init__(self, name: str, path_params: typing.Dict[str, typing.Any]) -> None:
        params = ",".join(path_params.keys())
        super().__init__(f"No route exists for name {name!r} and params {params!r}.")


class Match(enum.Enum):
    NONE = 0
    PARTIAL = 1
    FULL = 2


PARAM_REGEX = re.compile("{([a-zA-Z_][a-zA-Z0-9_]*)(:[a-zA-Z_][a-zA-Z0-9_]*)?}")


def compile_path(
    path: str,
) -> typing.Tuple[typing.Pattern, str, typing.Dict[str, Convertor]]:
    path_regex, path_format = "^", ""
    duplicated_params: typing.Set[str] = set()

    idx = 0
    param_converts = {}

    for match in PARAM_REGEX.finditer(path):
        param_name, convert_type = match.groups("str")
        convert_type = convert_type.lstrip(":")
        assert (
            convert_type in CONVERTOR_TYPES
        ), f'Unknown path convertor "{convert_type}"'
        convertor = CONVERTOR_TYPES[convert_type]

        path_regex += re.escape(path[idx : match.start()])
        path_regex += "(?P<%s>%s)" % (param_name, convertor.regex)

        path_format += path[idx : match.start()]
        path_format += "{%s}" % param_name

        if param_name in param_converts:
            duplicated_params.add(param_name)

        param_converts[param_name] = convertor

        idx = match.end()
    # endfor
    if duplicated_params:
        duplicated_params = sorted(duplicated_params)  # type: ignore
        names = ", ".join(duplicated_params)
        ending = "s" if len(duplicated_params) > 1 else ""
        raise ValueError(f"Duplicated param name{ending} {names} at path {path}")

    path_regex += re.escape(path[idx:]) + "$"
    path_format += path[idx:]

    return re.compile(path_regex), path_format, param_converts


class BaseRoute(object):
    """路由基本类，所有的路由类的实现必须是其的子类"""

    def matches(self, scope: Scope) -> typing.Tuple[Match, Scope]:
        """匹配路由"""
        raise NotImplementedError()

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        """生成URL"""
        raise NotImplementedError()

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """路由处理方法"""
        raise NotImplementedError()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """路由处理逻辑，在匹配路由后，转交处理权限给 handle"""
        match, child_scope = self.matches(scope)
        if match == Match.NONE:
            if scope["type"] == "http":
                res = PlainTextResponse("Not Found", status_code=404)
                await res(scope, receive, send)
            elif scope["type"] == "websocket":
                ws_close = WebSocketClose()
                await ws_close(scope, receive, send)
            return
        # end if
        scope.update(child_scope)  # type: ignore
        await self.handle(scope, receive, send)

    def __str__(self) -> str:
        return "%s(path=%s,endpoint=%s)" % (
            self.__class__.__name__,
            getattr(self, "path", ""),
            getattr(self, "name", ""),
        )


class Route(BaseRoute):
    """API 路由"""

    def __init__(
        self,
        path: str,
        endpoint: typing.Callable,
        *,
        methods: typing.Optional[typing.Sequence[str]] = None,
        name: typing.Optional[str] = None,
        include_in_schema: typing.Optional[bool] = True,
    ) -> None:
        """API 路由
        Args:
            path: 要挂载的 url path
            endpoint: url path 匹配的路由方法
            methods: http 请求方法，默认 ['GET']
            name: 路由名称
            include_in_schema: 是否要生成 OpenAPI 文档

        Returns:
            None

        Raises:
            None

        Examples:
            # todo: none
        """

        assert path.startswith("/"), 'Routed paths must always start "/"'
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name
        self.include_in_schema = include_in_schema

        endpoint_handler = endpoint
        while isinstance(endpoint_handler, functools.partial):
            endpoint_handler = endpoint_handler.func

        if inspect.isfunction(endpoint_handler) or inspect.ismethod(endpoint_handler):
            self.app = req_res(endpoint)
            if methods is None:
                methods = ["GET"]
        else:
            self.app = endpoint

        self.methods: typing.Optional[typing.Set] = None
        if methods is not None:
            self.methods = {method.upper() for method in methods}
            if "GET" in self.methods:
                self.methods.add("HEAD")

        (self.path_regex, self.path_format, self.param_convertors) = compile_path(path)

    def matches(self, scope: Scope) -> typing.Tuple[Match, Scope]:
        """路由匹配
        Args:
            scope: 请求上下文

        Returns:
            tuple(Match, Scope)

        Raises:
            None

        Examples:
            # todo: none
        """
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
            # end if
        # end if
        return Match.NONE, {}

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        seen_params = set(path_params.keys())
        excepted_params = set(self.param_convertors.keys())
        if name != self.name or seen_params != excepted_params:
            raise NoMatchFound(name, path_params)
        path, remaining_params = replace_params(
            self.path_format, self.param_convertors, path_params
        )
        return URLPath(protocol="http", path=path)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.methods and scope["method"] not in self.methods:
            headers = {"Allow": ", ".join(self.methods)}
            if "app" in scope:
                raise HttpException(status_code=405, headers=headers)
            else:
                res = PlainTextResponse(
                    "Method Not Allowed", status_code=405, headers=headers
                )
            await res(scope, receive=receive, send=send)
        else:
            await self.app(scope, receive=receive, send=send)  # type: ignore

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, Route)
            and self.path == other.path
            and self.endpoint == other.endpoint
            and self.methods == other.methods
        )


class WebSocketRoute(BaseRoute):
    """WebSocket 路由"""

    def __init__(
        self, path: str, endpoint: typing.Callable, *, name: typing.Optional[str] = None
    ) -> None:
        """WebSocket 路由
        Args:
            path: URL 路径
            endpoint: 路由处理端点，通常是业务处理方法
            name: 路由名称

        Returns:
            None

        Raises:
            None

        Examples:
            async def ws_endpoint(ss):
                await ss.accept()
                ...
                await ss.close()

            WebSocketRoute("/ws", endpoint=ws_endpoint),
        """
        assert path.startswith("/"), 'Routed paths must be always start "/"'
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name

        endpoint_handler = endpoint
        while isinstance(endpoint_handler, functools.partial):
            endpoint_handler = endpoint_handler.func

        if inspect.isfunction(endpoint_handler) or inspect.ismethod(endpoint_handler):
            self.app = ws_session(endpoint)
        else:
            self.app = endpoint

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
        """WebSocket URL
        Args:
            name: 生成路由`name` url path
            path_params: 路由参数, 例如: url_path_for(name=..., int=12, str='12')

        Returns:
            URLPath

        Raises:
            NoMatchFound: 当 路由`name`不匹配 时

        Examples:
            async def ws_endpoint(ss):
                await ss.accept()
                ...
                await ss.close()

            wsr = WebSocketRoute("/ws", endpoint=ws_endpoint)
            wsr.url_path_for(name='foo', foo_int=1, foo_str='foo')
        """

        seen_params = set(path_params.keys())
        expected_params = set(self.param_convertors.keys())
        if name != self.name or seen_params != expected_params:
            raise NoMatchFound(name, path_params)
        path, remaining_params = replace_params(
            self.path_format, self.param_convertors, path_params
        )
        assert not remaining_params
        return URLPath(protocol="websocket", path=path)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive=receive, send=send)  # type: ignore

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, WebSocketRoute)
            and self.path == other.path
            and self.endpoint == other.endpoint
        )


class Mount(BaseRoute):
    """挂载其他符合 asgi3 的应用"""

    def __init__(
        self,
        path: str,
        app: typing.Optional[ASGI3App] = None,
        routes: typing.Optional[typing.List[BaseRoute]] = None,
        name: typing.Optional[str] = None,
        *,
        middlewares: typing.Optional[
            typing.Sequence[typing.Tuple[Middleware, dict]]
        ] = None,
    ) -> None:
        """挂载其他符合 asgi3 的应用
        Args:
            path: 挂载 url 路径
            app: ASGI3App 处理回调函数
            routes: 挂载 route 列表
            name: route name
            middlewares: 处理中间件列表

        Returns:
            None

        Raises:
            None

        Examples:

        """
        assert path == "" or path.startswith("/"), 'Routed paths must always start "/"'
        assert (
            app is not None or routes is not None
        ), "`app=...` or `routes=[...]` must be specified one of them"
        self.path = path.rstrip("/")
        if app is not None:
            self._base_app: ASGI3App = app
        else:
            self._base_app = Router(routes=routes)

        self.app = self._base_app  # type: ignore

        for cls, options in reversed(middlewares or ()):
            if "debug" not in options:
                options["debug"] = False
            self.app = cls(app=self.app, **options)  # type: ignore

        self.name = name
        (self.path_regex, self.path_format, self.param_convertors) = compile_path(
            self.path + "/{path:path}"
        )

    @property
    def routes(self) -> typing.List[Route]:
        return getattr(self._base_app, "routes", [])

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
                root_path = scope.get("root_path", "")
                child_scope = {
                    "path_param": path_params,
                    "app_root_path": scope.get("app_root_path", root_path),
                    "root_path": root_path + matched_path,
                    "path": remaining_path,
                    "endpoint": self.app,
                }
                return Match.FULL, child_scope
        return Match.NONE, {}

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        """Mount URL
        Args:
            name: 生成路由`name` url path
            **path_params: 路由参数, 例如: url_path_for(name=..., int=12, str='12')

        Returns:
            URLPath

        Raises:
            NoMatchFound: 当 路由`name`不匹配 时

        Examples:
            m = Mount(...)
            m.url_path_for(name='foo', foo_int=1, foo_str='foo')
        """

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

            path_kwarg = path_params.get("path")
            path_params["path"] = ""

            path_prefix, remaining_params = replace_params(
                self.path_format, self.param_convertors, path_params
            )
            if path_kwarg is not None:
                remaining_params["path"] = path_kwarg
            for route in self.routes or []:
                try:
                    url = route.url_path_for(remaining_name, **remaining_params)
                    return URLPath(
                        protocol=url.protocol, path=path_prefix.rstrip("/") + str(url)
                    )
                except NoMatchFound:
                    pass

        raise NoMatchFound(name, path_params)

    async def handle(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:  # type: ignore
        await self.app(scope, receive, send)  # type: ignore

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, Mount)
            and self.path == other.path
            and self.app == other.app
        )


class Host(BaseRoute):
    """其他子域名挂载"""

    def __init__(
        self, host: str, app: ASGI3App, name: typing.Optional[str] = None
    ) -> None:
        """其他子域名挂载
        Args:
            host: 域名
            app: ASGI 应用
            name: 挂载点名称

        Returns:
            None

        Raises:
            None

        Examples:
            Host(
                "www.example.org",
                app=Router([Route(...), Route(...),]),
            )
        """

        self.host = host
        self.app = app
        self.name = name
        (self.host_regex, self.host_format, self.param_convertors) = compile_path(host)

    @property
    def routes(self) -> typing.Optional[typing.List[BaseRoute]]:
        return getattr(self.app, "routes", None)

    def matches(self, scope: Scope) -> typing.Tuple[Match, Scope]:
        if scope["type"] in ("http", "websocket"):
            headers = Headers(scope=scope)
            host = headers.get("host", "").split(":")[0]  # type: ignore
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
        """Host URL
        Args:
            name: 生成路由`name` url path
            **path_params: 路由参数, 例如: url_path_for(name=..., int=12, str='12')

        Returns:
            URLPath

        Raises:
            NoMatchFound: 当 路由`name`不匹配 时

        Examples:
            m = Host(...)
            m.url_path_for(name='foo', foo_int=1, foo_str='foo')
        """
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
        raise NoMatchFound(name, path_params)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive=receive, send=send)  # type: ignore

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, Host)
            and self.host == other.host
            and self.app == other.app
        )


class Router(object):
    """路由分组"""

    def __init__(
        self,
        routes: typing.Optional[typing.List[BaseRoute]] = None,
        redirect_slashes: typing.Optional[bool] = True,
        default: typing.Optional[ASGIApp] = None,
    ) -> None:
        """路由分组
        Args:
            routes: 路由列表
            redirect_slashes: 是否处理多余的 ‘/’
            default: 404 处理器

        Returns:
            None

        Raises:
            None
        """
        self.routes = [] if routes is None else list(routes)
        self.redirect_slashes = redirect_slashes
        self.default = self.not_found if default is None else default
        self._lifespan = None

    def mount(
        self, path: str, app: ASGI3App, name: typing.Optional[str] = None
    ) -> None:
        """
        @see app.mount
        """
        prefix = Mount(path, app=app, name=name)
        self.routes.append(prefix)

    def host(self, host: str, app: ASGI3App, name: typing.Optional[str] = None) -> None:
        """
        @see app.host
        """
        route = Host(host, app=app, name=name)
        self.routes.append(route)

    def route(
        self,
        path: str,
        methods: typing.Optional[typing.Sequence[str]] = None,
        name: typing.Optional[str] = None,
        include_in_schema: typing.Optional[bool] = True,
    ) -> typing.Callable:
        """
        @see app.route
        """

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

    def route_ws(self, path: str, name: typing.Optional[str] = None) -> typing.Callable:
        """
        @see app.ws_route
        """

        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_route_ws(path, func, name=name)
            return func

        return decorator

    def add_route(
        self,
        path: str,
        endpoint: typing.Callable,
        methods: typing.Optional[typing.Sequence[str]] = None,
        name: typing.Optional[str] = None,
        include_in_schema: typing.Optional[bool] = True,
    ) -> None:
        """
        @see app.add_route
        """
        instance = Route(
            path,
            endpoint=endpoint,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
        )
        self.routes.append(instance)

    def add_route_ws(
        self, path: str, route: typing.Callable, name: typing.Optional[str] = None
    ) -> None:
        """
        @see app.add_route_ws
        """
        instance = WebSocketRoute(path, name=name, endpoint=route)
        self.routes.append(instance)

    async def not_found(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await WebSocketClose()(scope, receive, send)
            return

        if "app" in scope:
            raise HttpException(status_code=404)
        await PlainTextResponse("Not Found", 404)(scope, receive, send)

    def url_path_for(self, name: str, **path_params: P.kwargs) -> URLPath:  # type: ignore
        for route in self.routes:
            try:
                return route.url_path_for(name=name, **path_params)
            except NoMatchFound:
                pass

        raise NoMatchFound(name, path_params)

    @property
    def lifespan(self) -> typing.Any:
        return self._lifespan

    @lifespan.setter
    def lifespan(self, lifespan: typing.Any) -> None:
        self._lifespan = lifespan

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] in ("http", "websocket", "lifespan")

        if "router" not in scope:
            scope["router"] = self  # type: ignore

        if scope["type"] == "lifespan" and self._lifespan is not None:
            await self._lifespan(scope, receive=receive, send=send)
            return

        partial = None

        for route in self.routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                scope.update(child_scope)  # type: ignore
                await route.handle(scope, receive=receive, send=send)
                return
            elif match == Match.PARTIAL and partial is None:
                partial = route
                partial_scope = child_scope

        if partial is not None:
            scope.update(partial_scope)  # type: ignore
            await partial.handle(scope, receive=receive, send=send)
            return

        if scope["type"] == "http" and self.redirect_slashes:
            if scope["path"].endswith("/"):
                redirect_path = scope["path"].rstrip("/")
            else:
                redirect_path = scope["path"] + "/"

            if redirect_path:
                redirect_scope = dict(scope)
                redirect_scope["path"] = redirect_path

                for route in self.routes:
                    match, child_scope = route.matches(redirect_scope)
                    if match != Match.NONE:
                        redirect_url = URL(scope=redirect_scope)
                        res = RedirectResponse(url=str(redirect_url))
                        await res(scope=scope, receive=receive, send=send)
                        return

        await self.default(scope, receive=receive, send=send)  # type: ignore

    def __eq__(self, other: typing.Any) -> bool:
        return isinstance(other, Router) and self.routes == other.routes


class ProtocalRouter(object):
    def __init__(self, protocals: typing.Dict[str, ASGIApp]) -> None:
        self.protocals = protocals

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.protocals[scope["type"]](scope, receive=receive, send=send)  # type: ignore


def req_res(func: typing.Callable) -> typing.Callable:
    is_coroutine = inspect.iscoroutinefunction(func)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        req = Request(scope, receive, send=send)
        if is_coroutine:
            res = await func(req)
        else:
            res = await run_in_threadpool(func, req)

        await res(scope, receive, send)

    return app


def ws_session(func: typing.Callable) -> typing.Callable:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        session = WebSocket(scope, receive, send)
        await func(session)

    return app


def get_name(endpoint: typing.Callable) -> str:
    if inspect.isroutine(endpoint) or inspect.isclass(endpoint):
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
