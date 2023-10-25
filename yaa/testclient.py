"""
module: TestClient
title: 测试客户端
description:
    用于测试 asgi http 请求 
author: emryslou@gmail.com
examples: @(file):test_client.py
exposes:
    - TestClient
"""
import contextlib
import http
import inspect
import io
import json
import math
import queue
import types
import typing
import warnings
from concurrent.futures import Future
from urllib.parse import unquote, urljoin

import anyio.abc
import httpx
from anyio.streams.stapled import StapledObjectStream

from yaa._utils import is_async_callable
from yaa.types import Message, P, Receive, Scope, Send
from yaa.websockets import WebSocketDisconnect

ASGIInstance = typing.Callable[[Receive, Send], typing.Awaitable[None]]
ASGI2App = typing.Callable[[Scope], ASGIInstance]
ASGI3App = typing.Callable[[Scope, Receive, Send], typing.Awaitable[None]]

_PortalFactoryType = typing.Callable[
    [], typing.ContextManager[anyio.abc.BlockingPortal]
]


class _Upgrade(Exception):
    def __init__(self, session: "WebSocketTestSession") -> None:
        self.session = session


def _get_reason_phrase(status_code: int) -> str:
    try:
        return http.HTTPStatus(status_code).phrase
    except ValueError:
        return ""


def _is_asgi3(app: typing.Union[ASGI2App, ASGI3App]) -> bool:
    if inspect.isclass(app):
        return hasattr(app, "__await__")
    return is_async_callable(app)


class _WrapASGI2:
    """
    Provide an ASGI3 interface onto an ASGI2 app.
    """

    def __init__(self, app: ASGI2App) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope)(receive, send)


class WebSocketTestSession(object):
    def __init__(
        self,
        app: ASGI3App,
        scope: Scope,
        portal_factory: _PortalFactoryType,
    ) -> None:
        self.app = app
        self.scope = scope
        self.accepted_subprotocol = None

        self.portal_factory = portal_factory

        self._receive_queue: queue.Queue[typing.Any] = queue.Queue(maxsize=100)
        self._send_queue: queue.Queue[typing.Any] = queue.Queue(maxsize=100)

        self.extra_headers = None

    def __enter__(self) -> "WebSocketTestSession":
        self.exit_stack = contextlib.ExitStack()
        self.portal = self.exit_stack.enter_context(self.portal_factory())

        try:
            _: "Future[None]" = self.portal.start_task_soon(self._run)
            self.send({"type": "websocket.connect"})
            message = self.receive()
            self._raise_on_close(message)
        except Exception:
            self.exit_stack.close()
            raise

        self.accepted_subprotocol = message.get("subprotocol", None)
        self.extra_headers = message.get("headers", None)
        return self

    def __exit__(self, *args: P.args, **kwargs: P.kwargs) -> None:
        try:
            self.close(1000)
        finally:
            self.exit_stack.close()

        while not self._send_queue.empty():
            message = self._send_queue.get()
            if isinstance(message, BaseException):
                raise message  # pragma: nocover

    async def _run(self) -> None:
        scope = self.scope
        receive = self._asgi_receive
        send = self._asgi_send
        try:
            await self.app(scope, receive, send)
        except BaseException as exc:
            self.__sput(exc)

    async def _asgi_receive(self) -> typing.Any:
        while self._receive_queue.empty():
            await anyio.sleep(0)
        return self._receive_queue.get()

    async def _asgi_send(self, message: typing.Any) -> None:
        self.__sput(message)

    def _raise_on_close(self, message: typing.Any) -> None:
        if message["type"] == "websocket.close":
            raise WebSocketDisconnect(
                message.get("code", 1000), message.get("reason", "")
            )

    def send(self, value: typing.Any) -> None:
        self._receive_queue.put(value)

    def send_text(self, data: str) -> None:
        self.send({"type": "websocket.receive", "text": data})

    def send_bytes(self, data: bytes) -> None:
        self.send({"type": "websocket.receive", "bytes": data})

    def send_json(self, data: typing.Any) -> None:
        _j = json.dumps(data).encode("utf-8")
        self.send_bytes(_j)

    def close(self, code: int = 1000) -> None:
        self.send({"type": "websocket.disconnect", "code": code})

    def receive(self) -> typing.Any:
        message = self._send_queue.get()
        if isinstance(message, BaseException):
            raise message
        return message

    def receive_text(self) -> str:
        message = self.receive()
        self._raise_on_close(message)
        return str(message["text"])

    def receive_bytes(self) -> bytes:
        message = self.receive()
        self._raise_on_close(message)
        return message["bytes"]

    def receive_json(self) -> typing.Any:
        return json.loads(self.receive_bytes().decode("utf-8"))

    def __sput(self, message: typing.Any) -> None:
        if message is None:
            raise RuntimeError("value is None")  # pragma: nocover
        self._send_queue.put(message)


class _TestClientTransport(httpx.BaseTransport):
    def __init__(
        self,
        app: ASGI3App,
        portal_factory: _PortalFactoryType,
        raise_server_exceptions: bool = True,
        root_path: str = "",
        *,
        app_state: typing.Dict[str, typing.Any],
    ) -> None:
        self.app = app
        self.raise_server_exceptions = raise_server_exceptions
        self.root_path = root_path
        self.portal_factory = portal_factory
        self.app_state = app_state

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        scheme = request.url.scheme
        netloc = request.url.netloc.decode(encoding="ascii")
        path = request.url.path
        raw_path = request.url.raw_path
        query = request.url.query.decode(encoding="ascii")

        default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[str(scheme)]
        port: int
        if ":" in netloc:
            host, _port = netloc.split(":", 1)
            port = int(_port)
        else:
            host = netloc
            port = int(default_port)

        # Include the 'host' header.
        if "host" in request.headers:
            headers = []
        elif port == default_port:
            headers = [[b"host", host.encode()]]
        else:
            headers = [[b"host", (f"{host}:{port}").encode()]]

        # Include other request headers.
        headers += [
            [key.lower().encode(), value.encode()]
            for key, value in request.headers.items()
        ]

        if scheme in {"ws", "wss"}:
            subprotocol = request.headers.get("sec-websocket-protocol", None)

            if subprotocol is None:
                subprotocols = []
            else:
                subprotocols = [val.strip() for val in subprotocol.split(",")]

            scope = {
                "type": "websocket",
                "path": unquote(path),
                "raw_path": raw_path,
                "root_path": self.root_path,
                "scheme": scheme,
                "query_string": query.encode(),
                "headers": headers,
                "client": ["testclient", 50000],
                "server": [host, port],
                "subprotocols": subprotocols,
                "state": self.app_state.copy(),
            }
            session = WebSocketTestSession(self.app, scope, self.portal_factory)
            raise _Upgrade(session)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": request.method,
            "path": unquote(path),
            "raw_path": raw_path,
            "root_path": self.root_path,
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": ["testclient", 50000],
            "server": [host, port],
            "extensions": {"http.response.template": {}, "http.response.debug": {}},
            "state": self.app_state.copy(),
        }

        request_complete = False
        response_started = False
        response_complete: anyio.Event
        raw_kwargs: typing.Dict[str, typing.Any] = {"stream": io.BytesIO()}
        template = None
        context = None

        async def receive() -> typing.Mapping[str, typing.Any]:
            nonlocal request_complete
            if request_complete:
                if not response_complete.is_set():
                    await response_complete.wait()
                return {"type": "http.disconnect"}

            body = request.read()
            if isinstance(body, str):
                body_bytes = body.encode("utf-8")  # type: bytes
            elif body is None:
                body_bytes = b""
            elif isinstance(body, types.GeneratorType):
                try:
                    chunk = body.send(None)
                    if isinstance(chunk, str):
                        chunk = chunk.encode("utf-8")
                    return {"type": "http.request", "body": chunk, "more_body": True}
                except StopIteration:
                    request_complete = True
                    return {
                        "type": "http.request",
                        "body": b"",
                    }
            else:
                body_bytes = body

            request_complete = True
            return {"type": "http.request", "body": body_bytes}

        async def send(message: Message) -> None:
            nonlocal raw_kwargs, response_started
            nonlocal template, context
            if message["type"] == "http.response.start":
                assert (
                    not response_started
                ), 'Received multiple "http.response.start" messages'

                raw_kwargs["status_code"] = message["status"]
                raw_kwargs["headers"] = [
                    (key.decode(), value.decode())
                    for key, value in message.get("headers", [])
                ]
                response_started = True
            elif message["type"] == "http.response.body":
                assert (
                    response_started
                ), 'Received "http.response.body" without "http.response.start".'
                assert (
                    not response_complete.is_set()
                ), 'Received "http.response.body" after response completed'
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if request.method != "HEAD":
                    raw_kwargs["stream"].write(body)

                if not more_body:
                    raw_kwargs["stream"].seek(0)
                    response_complete.set()
            elif message["type"] == "http.response.template":
                template = message["template"]
                context = message["context"]
            elif message["type"] == "http.response.debug":
                template = message["info"]["template"]
                context = message["info"]["context"]

        try:
            with self.portal_factory() as portal:
                response_complete = portal.call(anyio.Event)
                portal.call(self.app, scope, receive, send)
        except BaseException as exc:
            if self.raise_server_exceptions:
                raise exc

        if self.raise_server_exceptions:
            assert response_started, "TestClient did not receive any response"
        elif not response_started:
            raw_kwargs = {
                "status_code": 500,
                "headers": [],
                "stream": io.BytesIO(),
            }
        raw_kwargs["stream"] = httpx.ByteStream(raw_kwargs["stream"].read())
        res = httpx.Response(**raw_kwargs, request=request)
        if template is not None:
            res.template = template  # type: ignore[attr-defined]
            res.context = context  # type: ignore[attr-defined]

        return res


class TestClient(httpx.Client):
    """测试客户端
    Attrs:
        __test__: 是否开启测试，暂时没有用到
        user_agent: 请求 user_agent
        base_url: 请求 url 前缀
    
    """
    __test__ = False

    user_agent: str = "testclient"
    base_url: str = "http://testserver"  # type: ignore[assignment]

    portal: typing.Optional[anyio.abc.BlockingPortal] = None

    async_backend: typing.Mapping[str, typing.Any] = {
        "backend": "asyncio",
        "backend_options": {},
    }

    task: Future[None]

    def __init__(
        self,
        app: typing.Union[ASGI2App, ASGI3App],
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        backend: str = "asyncio",
        backend_options: typing.Mapping[str, typing.Any] = {},
        cookies: typing.Optional[httpx._client.CookieTypes] = None,  # type: ignore[name-defined]
        headers: typing.Optional[typing.Dict[str, str]] = None,
        follow_redirects: bool = True,
    ) -> None:
        """测试客户端
        Args:
            app: ASGI 应用程序
            base_url: 请求基础URL, 例如: 请求 path = `/path/to`, 则完整的请求URL为`{base_url}/path/to`
            raise_server_exceptions: 是需要抛出异常
            root_path: 请求根path，请求 path = `/path/to`, 则完整的请求URL为`{base_url}/{root_path}/path/to`
            backend: anyio 启动配置
            backend_options: anyio 启动配置
            cookie: 请求cookie
            headers: headers
            follow_redirects: 是否重定向
        
        Returns:
            None
        
        Raises:
            None
        
        Examples:
            app = Yaa(...)
            client = TestClient(app=app)
            client.get(...)
        """
        self.async_backend["backend"] = backend  # type: ignore[index]
        self.async_backend["backend_options"] = backend_options  # type: ignore[index]

        if _is_asgi3(app):
            app = typing.cast(ASGI3App, app)
            asgi_app = app
        else:
            app = typing.cast(ASGI2App, app)
            asgi_app = _WrapASGI2(app)

        self.base_url = base_url
        self.app = asgi_app
        self.app_state: typing.Dict[str, typing.Any] = {}

        transport = _TestClientTransport(
            app=self.app,
            portal_factory=self._portal_factory,
            raise_server_exceptions=raise_server_exceptions,
            root_path=root_path,
            app_state=self.app_state,
        )
        if headers is None:
            headers = {}

        headers.setdefault("user-agent", self.user_agent)
        super().__init__(
            app=self.app,
            base_url=self.base_url,
            headers=headers,
            transport=transport,
            follow_redirects=follow_redirects,
            cookies=cookies,
        )

    @contextlib.contextmanager
    def _portal_factory(self) -> typing.Generator[anyio.abc.BlockingPortal, None, None]:
        if self.portal is not None:
            yield self.portal
        else:
            with anyio.from_thread.start_blocking_portal(
                **self.async_backend
            ) as portal:
                # self.portal = portal
                yield portal

    def _choose_redirect_arg(
        self,
        follow_redirects: typing.Optional[bool],
        allow_redirects: typing.Optional[bool],
    ) -> typing.Union[bool, httpx._client.UseClientDefault]:
        redirect: typing.Union[
            bool, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT

        if allow_redirects is not None:
            message = (
                "The `allow_redirects` argment is deprecated."
                "Use `allow_redirects` instead."
            )
            warnings.warn(message, DeprecationWarning)
            redirect = allow_redirects

        if follow_redirects is not None:
            redirect = follow_redirects
        elif allow_redirects is not None and follow_redirects is not None:
            raise RuntimeError(
                "Cannot use both `allow_redirects` and `follow_redirects`."
            )

        return redirect

    def request(  # type: ignore[override]
        self,
        method: str,
        url: httpx._types.URLTypes,
        *,
        content: typing.Optional[httpx._types.RequestContent] = None,
        data: typing.Optional[httpx._types.RequestData] = None,
        files: typing.Optional[httpx._types.RequestFiles] = None,
        json: typing.Optional[typing.Any] = None,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Optional[
            typing.Union[httpx._types.AuthTypes, httpx._client.UseClientDefault]
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes,
            httpx._client.UseClientDefault,
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[dict] = None,
    ) -> httpx.Response:
        """发起 HTTP 请求"""

        url = urljoin(self.base_url, url)  # type: ignore
        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().request(
            method,
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def get(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Optional[
            typing.Union[httpx._types.AuthTypes, httpx._client.UseClientDefault]
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes,  # type: ignore[name-defined]
            httpx._client.UseClientDefault,  # type: ignore[name-defined]
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[dict] = None,
    ) -> httpx.Response:  # type: ignore
        """发起 HTTP 请求: get"""

        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().get(
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,  # type: ignore[arg-type]
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def options(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[dict] = None,
    ) -> httpx.Response:  # type: ignore
        """发起 HTTP 请求: option"""

        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().options(
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def head(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[dict] = None,
    ) -> httpx.Response:  # type: ignore
        """发起 HTTP 请求: head"""

        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().head(
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def post(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        content: typing.Optional[httpx._types.RequestContent] = None,
        data: typing.Optional[httpx._types.RequestData] = None,
        files: typing.Optional[httpx._types.RequestFiles] = None,
        json: typing.Optional[typing.Any] = None,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Optional[
            typing.Union[httpx._types.AuthTypes, httpx._client.UseClientDefault]
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[dict] = None,
    ) -> httpx.Response:  # type: ignore
        """发起 HTTP 请求: post"""

        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().post(
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,  # type: ignore[arg-type]
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def put(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        content: typing.Optional[httpx._types.RequestContent] = None,
        data: typing.Optional[httpx._types.RequestData] = None,
        files: typing.Optional[httpx._types.RequestFiles] = None,
        json: typing.Optional[typing.Any] = None,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Optional[
            typing.Union[httpx._types.AuthTypes, httpx._client.UseClientDefault]
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[dict] = None,
    ) -> httpx.Response:  # type: ignore
        """发起 HTTP 请求: put"""

        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().put(
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,  # type: ignore[arg-type]
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def patch(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        content: typing.Optional[httpx._types.RequestContent] = None,
        data: typing.Optional[httpx._types.RequestData] = None,
        files: typing.Optional[httpx._types.RequestFiles] = None,
        json: typing.Optional[typing.Any] = None,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Optional[
            typing.Union[httpx._types.AuthTypes, httpx._client.UseClientDefault]
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[dict] = None,
    ) -> httpx.Response:  # type: ignore
        """发起 HTTP 请求: put"""

        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().patch(
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,  # type: ignore[arg-type]
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def delete(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[dict] = None,
    ) -> httpx.Response:  # type: ignore
        """发起 HTTP 请求: delete"""

        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().delete(
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def wsconnect(
        self, url: str, subprotocols: typing.Optional[str] = None, **kwargs: typing.Any
    ) -> WebSocketTestSession:
        """创建 WebSocket 连接
        Args:
            url: WebSocket URL Path
            subprotocols: 子协议
            **kwargs: 其他请求参数
        
        Returns:
            WebSocketTestSession
        
        Raises:
            None
        
        Examples:
            client = TestClient(...)
            with client.wsconnect('/path') as ws:
                msg = 'some message'
                ws.send_bytes(msg.encode("utf-8"))
                ws.receive_bytes() == (f"Received msg is {msg}").encode("utf-8")
            # 说明:
            # ws.send -- 发送数据
            # ws.send_text -- 发送文本
            # ws.send_bytes -- 发送字节
            # ws.send_json  -- 发送JSON
            # ws.receive -- 接收数据
            # ws.receive_text -- 接收文本
            # ws.receive_bytes -- 接收字节
            # ws.receive_json  -- 接收JSON
        """
        url = urljoin("ws://testserver", url)
        headers = kwargs.get("headers", {})
        headers.setdefault("connection", "upgrade")
        headers.setdefault("sec-websocket-key", "testserver==")
        headers.setdefault("sec-websocket-version", "13")
        if subprotocols is not None:
            headers.setdefault("sec-websocket-protocol", ",".join(subprotocols))

        kwargs["headers"] = headers

        try:
            self.request("GET", url, **kwargs)
        except _Upgrade as exc:
            return exc.session
        else:
            raise RuntimeError("Expected WebSocket upgrade")  # pragma: no cover

    def __enter__(self) -> "TestClient":
        with contextlib.ExitStack() as stack:
            self.portal = portal = stack.enter_context(
                anyio.from_thread.start_blocking_portal(**self.async_backend)  # type: ignore
            )

            @stack.callback
            def reset_portal() -> None:
                self.portal = None

            self.stream_send = StapledObjectStream(
                *anyio.create_memory_object_stream(math.inf)
            )  # type: ignore[var-annotated]
            self.stream_receive = StapledObjectStream(
                *anyio.create_memory_object_stream(math.inf)
            )  # type: ignore[var-annotated]

            self.task = portal.start_task_soon(self.lifespan)
            portal.call(self.wait_startup)

            @stack.callback
            def wait_shutdown() -> None:
                portal.call(self.wait_shutdown)

            self.exit_stack = stack.pop_all()

        return self

    def __exit__(self, *args: typing.Any) -> None:
        self.exit_stack.close()

    async def lifespan(self) -> None:
        try:
            await self.app(
                {"type": "lifespan", "state": self.app_state},
                self.stream_receive.receive,  # self.receive_queue.get,
                self.stream_send.send,  # self.send_queue.put
            )
        finally:
            await self.stream_send.send(None)

    async def wait_startup(self) -> None:
        await self.stream_receive.send({"type": "lifespan.startup"})

        async def receive() -> typing.Any:
            message = await self.stream_send.receive()
            if message is None:
                self.task.result()
            return message

        message = await receive()
        assert message["type"] in (
            "lifespan.startup.complete",
            "lifespan.startup.failed",
        )
        if message["type"] == "lifespan.startup.failed":
            await receive()

    async def wait_shutdown(self) -> None:
        async def receive() -> typing.Any:
            message = await self.stream_send.receive()
            if message is None:
                self.task.result()
            return message

        async with self.stream_send:
            await self.stream_receive.send({"type": "lifespan.shutdown"})
            message = await receive()
            assert message["type"] in (
                "lifespan.shutdown.complete",
                "lifespan.shutdown.failed",
            )
            if message["type"] == "lifespan.shutdown.failed":
                await receive()
