"""
module: Application
title: 框架初始化和启动
description:
    框架初始化和启动
author: emryslou@gmail.com
examples: test_applications.py
"""
import typing

from yaa._utils import get_logger
from yaa.datastructures import State, URLPath
from yaa.exceptions import ParameterException
from yaa.middlewares import BaseHttpMiddleware, Middleware
from yaa.routing import BaseRoute, Router
from yaa.types import ASGI3App, Lifespan, Receive, Scope, Send

logger = get_logger(__name__)


class Yaa(object):
    """Yaa"""

    def __init__(
        self,
        routes: typing.Optional[typing.List[BaseRoute]] = None,
        middlewares: typing.Optional[
            typing.List[typing.Tuple[Middleware, dict]]
        ] = None,
        exception_handlers: typing.Optional[
            typing.Dict[typing.Union[int, typing.Type[Exception]], typing.Callable]
        ] = None,
        on_startup: typing.Optional[typing.List[typing.Callable]] = None,
        on_shutdown: typing.Optional[typing.List[typing.Callable]] = None,
        lifespan: typing.Optional[Lifespan] = None,
        debug: bool = False,
        **kwargs,
    ) -> None:
        """Yaa 初始化
        Args:
            routes: 路由列表
            middlewares: 中间件列表，例如: [(FooMiddleware, {foo=..,boo=...,...})]
            exception_handlers: 异常处理器，例如 {http_status_code: call_for_status, MyException: call_for_exc}
            on_startup: 服务启动前回调方法列表
            on_shutdown: 服务关闭前回调方法列表
            lifespan: 服务开始前后回调对象, lifespan or on_startup/on_shutdown 而选其一
            debug: 是否开启调试，默认 False
        Returns:
            None
        
        Raises:
            None
        
        Examples:
            # for routes
            app = Yaa(
                ...,
                routes=[Route(...), Router(...), Host(...), Mount(...), WebSocketRoute(...)],
                ...,
            )

            # for middlewares
            app = Yaa(
                ...,
                middlewares=[(FooMiddleware, {foo=..,boo=...,...})]
                ...
            )

            # for exception_handlers
            app = Yaa(
                ...,
                exception_handlers= {
                    404: handle_for_404,
                    MyException: handle_for_my_exc,
                }
                ...
            )

            # for on_startup / on_shutdown
            app = Yaa(
                ...,
                on_startup = [su_fn1, su_fn2, ....],
                on_shutdown = [sd_fn1, sd_fn2, ....],
                ...
            )

            # for lifespan
            app = Yaa(
                ...,
                lifespan = DefaultLifespan
                ...
            )
        """

        self._debug = debug
        self.state = State()
        self.router = Router(routes=routes)
        self.app = self.router
        self.config: typing.Dict[str, typing.Any]
        self._init_config(
            lifespan=lifespan, on_startup=on_startup, on_shutdown=on_shutdown
        )

        self.exception_handlers = (
            {} if exception_handlers is None else dict(exception_handlers)
        )
        self.user_middlewares = [] if middlewares is None else list(middlewares)
        for _k, _cfg in kwargs.pop("plugins", {}).items():
            if _k in self.config["plugins"]:
                self.config["plugins"][_k].update(_cfg)  # type: ignore
            else:
                self.config["plugins"][_k] = _cfg  # type: ignore
        if len(kwargs) > 0:
            logger.debug(f'kwargs: {kwargs!r}')
            _arg_keys = ','.join(kwargs.keys())
            raise ParameterException(f'Unknown Params {_arg_keys!r}')
        self._init_plugins(self.config.get("plugins", {}))
        self.build_middleware_stack()

    def _init_config(
        self,
        lifespan: typing.Optional[Lifespan] = None,
        on_startup: typing.Optional[list] = None,
        on_shutdown: typing.Optional[list] = None,
    ) -> None:
        self.config = {
            "plugins": {
                "exceptions": {
                    "middlewares": {
                        "exception": dict(debug=self.debug),
                        "servererror": dict(debug=self.debug),
                    },
                },
                "lifespan": {
                    "event_handlers": {
                        "startup": [],
                        "shutdown": [],
                    },
                    "context": None,
                },
            },
        }

        assert lifespan is None or (
            on_shutdown is None and on_startup is None
        ), "Use either `lifespan` or `on_startup`/`on_shutdown`, not both"
        if lifespan is not None:
            self.config["plugins"]["lifespan"]["context"] = lifespan  # type: ignore
            self.config["plugins"]["lifespan"]["event_handlers"] = {}  # type: ignore
        else:
            if on_startup is not None:
                self.config["plugins"]["lifespan"]["event_handlers"][  # type: ignore
                    "startup"
                ] += on_startup
            if on_shutdown is not None:
                self.config["plugins"]["lifespan"]["event_handlers"][  # type: ignore
                    "shutdown"
                ] += on_shutdown

    def _init_plugins(self, plugins_config: dict = {}) -> None:
        _all_plugins = {}
        import importlib
        import os

        module_name = "yaa.plugins"
        module = importlib.import_module(module_name)
        plugin_middlewares = getattr(module, "plugin_middlewares")
        plugin_middlewares.clear()

        scan_path = os.path.dirname(module.__file__)  # type: ignore
        for file in os.listdir(scan_path):
            package_path = os.path.join(scan_path, file)  # type: ignore
            if not os.path.isdir(package_path) or package_path.endswith("__"):
                continue
            sub_module = importlib.import_module(f"{module_name}.{file}")
            if hasattr(sub_module, "plugin_init"):
                plugin_name = sub_module.__name__.replace(module_name, "").lstrip(".")
                _all_plugins[plugin_name] = sub_module.plugin_init

        for plugin_name, plugin_cfg in plugins_config.items():
            if plugin_name in _all_plugins:
                init_fn = _all_plugins[plugin_name]
                init_fn(self, plugin_cfg)

    def build_middleware_stack(self) -> None:
        """重建中间件调用堆栈"""
        app = self.app
        from yaa.plugins import plugin_middlewares as pmw

        key_srv = "yaa.plugins.exceptions.servererror"
        key_exc = "yaa.plugins.exceptions.exception"
        (srv, srv_options) = pmw.middlewares.get(key_srv)  # type: ignore[misc]
        (exc, exc_options) = pmw.middlewares.get(key_exc)  # type: ignore[misc]

        for _type, _handler in (self.exception_handlers or {}).items():
            if _type in (500, Exception):
                srv_options["handler"] = _handler
            else:
                if "handlers" in srv_options:
                    exc_options["handlers"][_type] = _handler
                else:
                    exc_options["handlers"] = {_type: _handler}
        middlewares = (
            [(srv, srv_options)]
            + [
                middleware
                for _k, middleware in pmw.middlewares.items()
                if _k not in (key_srv, key_exc)
            ]
            + self.user_middlewares
            + [(exc, exc_options)]
        )
        for cls, options in reversed(middlewares):
            if "debug" not in options:
                options["debug"] = self.debug
            app = cls(app=app, **options)
        self.middleware_app = app

    @property
    def routes(self) -> typing.List[BaseRoute]:
        """获取路由列表"""
        return self.router.routes

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, val: bool) -> None:
        self._debug = val

    def mount(
        self, path: str, app: ASGI3App, name: typing.Optional[str] = None
    ) -> None:
        """挂载 ASGI 应用到指定 url 路径
        Args:
            path: URL 路径
            app: ASGI 应用，类似: fn(scope: dict, receive: Callable, send: Callable)
            name: 挂载路由名称

        Returns:
            None
        
        Raises:
            None
        
        Examples:
            app = Yaa(...)
            app.mount('/static', StaticFiles(directory='demo/static'))
        """

        assert app != self
        self.router.mount(path, app=app, name=name)

    def host(self, host: str, app: ASGI3App, name: typing.Optional[str] = None) -> None:
        """挂载 ASGI 应用到指定 主机
        Args:
            host: 主机
            app: ASGI 应用，类似: fn(scope: dict, receive: Callable, send: Callable)
            name: 挂载路由名称

        Returns:
            None
        
        Raises:
            None
        
        Examples:
            #todo
        """
        
        assert app != self
        self.router.host(host, app=app, name=name)

    def add_route(
        self,
        path: str,
        route: typing.Union[typing.Callable, BaseRoute],
        methods: typing.Optional[list[str]] = None,
        name: typing.Optional[str] = None,
        include_in_schema: bool = True,
    ) -> None:
        """增加路由
        Args:
            path: URL 路径
            route: 业务方法，或者路由对象
            methods: HTTP请求方式: GET, POST, ...
            name: 路由名称
            include_in_schema: 是否创建 OpenAPI 文档
        
        Returns:
            None
        
        Raises:
            None
        
        Examples:
            app = Yaa(...)
            app.add_route('/path/to', Route(...))
        """
        self.router.add_route(
            path, route, methods=methods, name=name, include_in_schema=include_in_schema
        )

    def add_route_ws(
        self, path: str, route: typing.Union[typing.Callable, BaseRoute]
    ) -> None:
        """添加 WebSocket 路由
        Args:
            path: URL 路径
            route: 业务方法，或者路由对象
        
        Returns:
            None
        
        Raises:
            None
        
        Examples:
            app = Yaa(...)
            app.add_route_ws('/path/to', yaa.endpoints.WebSocketEndpoint(...))
        """
        self.router.add_route_ws(path, route)

    def add_middleware(
        self,
        middleware_class_or_func: typing.Union[type, typing.Callable],
        **kwargs: typing.Any,
    ) -> None:
        """添加中间件
        Args:
            middleware_class_or_func: 中间件对象
            **kwargs: 中间件对象初始化所需参数
        
        Returns:
            None
        
        Raises:
            None
        
        Examples:
            app = Yaa(...)
            app.add_middleware(MyMiddleware)
            app.add_middleware(NewMiddleware, foo=1)
            app.add_middleware(NewAgainMiddleware, boo='boo', foo=111)
        """
        self.user_middlewares.append((middleware_class_or_func, kwargs))  # type: ignore
        self.build_middleware_stack()

    def route(
        self,
        path: str,
        methods: typing.Optional[list[str]] = None,
        name: typing.Optional[str] = None,
        include_in_schema: bool = True,
    ) -> typing.Callable:
        """路由装饰器
        Args:
            path: URL 路径
            methods: HTTP请求方式: GET, POST, ...
            name: 路由名称
            include_in_schema: 是否创建 OpenAPI 文档
        
        Returns:
            None
        
        Raises:
            None
        
        Examples:
            app = Yaa(...)
            @app.`route`('/path/to/foo')
            def foo(request: Request) -> Response:
                ...
                return Response(...)
        """

        def decorator(func: typing.Callable) -> typing.Callable:
            self.router.add_route(
                path, func, methods, name=name, include_in_schema=include_in_schema
            )
            return func

        return decorator

    def ws_route(self, path: str, name: typing.Optional[str] = None) -> typing.Callable:
        """挂载WebSocket路由，该方法仅做装饰器使用
        Args:
            path: 要绑定的url path
            name: 路由名称
        Returns:
            typing.Callable
        Raises:
            None
        Examples:
            app = Yaa(...)
            @app.`ws_route`('/path/to/ws')
            def fun_ws(session: yaa.websockets.WebSocket) -> None:
                await session.accept()
                await session.send_text("Hello, world!")
                await session.close()
        """
        def decorator(func: typing.Callable) -> typing.Callable:
            self.router.add_route_ws(path, func, name=name)
            return func

        return decorator

    def middleware(self, middleware_type: str) -> typing.Callable:
        """添加中间件装饰器
        Args:
            middleware_type: 中间件类型，目前仅支持 `http`
        
        Returns:
            typing.Callable
        
        Raises:
            None
        
        Examples:
            app = Yaa()
            @app.middleware('http')
            async def middleware_demo_func(
                req: Request,
                call_next: typing.Awaitable[Response]
            ) -> Response:
                ...
                res = await some_reqres_func(req)
                return res
        """
        assert middleware_type == "http", 'Current only middleware("http") is supported'

        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_middleware(BaseHttpMiddleware, dispatch=func)

            return func

        return decorator

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        """生成路由`name` url path
        Args:
            name: 生成路由`name` url path
            path_params: 路由参数, 例如: url_path_for(..., int=12, str='12')
        
        Returns:
            URLPath
        
        Raises:
            NoMatchFound: 当 路由`name`不匹配 时
        
        Examples:
            app = Yaa()
            app.url_path_for(name=..., some_int=12, some_str='1234')
        """
        logger.debug(f"{__name__}::{self.__class__.__name__}::url_path_for {name}")
        return self.router.url_path_for(name=name, **path_params)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # type: ignore
        scope["app"] = self  # type: ignore
        await self.middleware_app(scope, receive, send)
