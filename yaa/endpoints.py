"""
module: Endpoints
title: 端点
description: 提供了 Http 和 WebSocket 请求处理的基础类模版
author: emryslou@gmail.com
examples: @(file):test_endpoints.py
exposes:
    - HttpEndPoint: Http 端点，可为 http 请求自动转发 不同 method 的请求
    - WebSocketEndpoint: WebSocket 端点，可自动处理不同类型的数据接收和发送
"""

import typing

import yaa.status as status
from yaa._utils import is_async_callable
from yaa.concurrency import run_in_threadpool
from yaa.exceptions import HttpException
from yaa.requests import Request
from yaa.responses import PlainTextResponse, Response
from yaa.types import Message, Receive, Scope, Send
from yaa.websockets import WebSocket

try:
    import ujson as json  # type: ignore[no-redef]
except ImportError:  # pragma: no cover
    import json  # type: ignore[no-redef] # pragma: no cover


class _Endpoint(object):
    _type = ""

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == self._type
        self._scope = scope
        self._receive = receive
        self._send = send
        self._allow_methods = [
            method
            for method in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
            if getattr(self, method.lower(), None) is not None
        ]

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    async def dispatch(self) -> None:
        raise NotImplementedError()

    async def method_not_allowed(self, req: Request) -> Response:
        headers = {"Allow": ", ".join(self._allow_methods)}
        if "app" in self._scope:
            raise HttpException(status_code=405, headers=headers)

        return PlainTextResponse("Method Not Allowed", status_code=405, headers=headers)


class HttpEndPoint(_Endpoint):
    """Http 端点
    Attrs:
        _type: 端点类型，固定: http
    """

    _type = "http"

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Http 端点初始化
        Args:
            scope: 请求上下文
            receive: 数据接收器
            send: 数据发送器

        Returns:
            None

        Raises:
            None

        Examples:
            class SomeHttpEndPoint(HttpEndPoint):
                # for http method: get
                def get(request: Request) -> Response:
                    ...
                    return Response(...)

                # for http method: post
                async def post(request: Request) -> Response:
                    ...
                    return Response(...)
        """
        super().__init__(scope, receive, send)

    async def dispatch(self) -> None:
        req = Request(self._scope, receive=self._receive)

        handler_name = (
            "get"
            if req.method == "HEAD" and not hasattr(self, "head")
            else req.method.lower()
        )
        handler = getattr(self, handler_name, self.method_not_allowed)
        if is_async_callable(handler):
            res = await handler(req)
        else:
            res = await run_in_threadpool(handler, req)

        await res(self._scope, self._receive, self._send)


class WebSocketEndpoint(_Endpoint):
    """WebSocket 终端
    Attrs:
        _type: 端点类型，固定: websocket
        encoding: 接收数据类型: text, bytes, json, 实现子类是必须定义， 不能为 None
        ws: WebSocket 对象，dispatch 方法会自动初始化
    """

    _type = "websocket"
    encoding = None  # 'text', 'bytes', 'json'
    ws: WebSocket

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """WebSocket 终端初始化
        Args:
            scope: 请求上下文
            receive: 数据接收器
            send: 数据发送器

        Returns:
            None

        Raises:
            None

        Examples:
            class MyWebSocketEndpoint(WebSocketEndpoint):
                encoding = "json"

                async def on_receive(self, data) -> None:
                    await self.send(data, send_type="json")
                    ...

                async def on_disconnect(self, code: int) -> None:
                    ...
        """
        super().__init__(scope, receive, send)

    async def dispatch(self) -> None:
        self.ws = WebSocket(self._scope, self._receive, self._send)
        kwargs = self._scope.get("kwargs", {})
        await self.on_connect(**kwargs)

        close_code = status.WS_1000_NORMAL_CLOSURE
        try:
            while True:
                message = await self.ws.receive()
                if message["type"] == "websocket.receive":
                    data = await self.decode(message)
                    await self.on_receive(data)
                elif message["type"] == "websocket.disconnect":
                    close_code = int(message.get("code", status.WS_1000_NORMAL_CLOSURE))
                    break
        except Exception as exc:  # pragma: nocover
            close_code = status.WS_1011_INTERNAL_ERROR  # pragma: nocover
            raise exc  # pragma: nocover
        finally:
            await self.on_disconnect(close_code)

    async def send(self, data: typing.Any, send_type: str = "bytes") -> None:
        fn = getattr(self.ws, "send_" + send_type)
        await fn(data)

    async def decode(self, message: Message) -> typing.Any:
        if self.encoding is not None:
            decode_fn_name = "_decode_" + self.encoding.lower()
            if not hasattr(self, decode_fn_name):
                decode_fn_name = "_decode_unknown"  # pragma: nocover
        else:
            decode_fn_name = "_decode_none"  # pragma: nocover

        decode_fn = getattr(self, decode_fn_name)
        return await decode_fn(message)

    async def _decode_text(self, message: Message) -> str:
        if "text" not in message:
            await self.ws.close(status.WS_1003_UNSUPPORTED_DATA)  # pragma: nocover
            raise RuntimeError(
                "Expected text websocket messages, but got others"
            )  # pragma: nocover
        return message["text"]

    async def _decode_bytes(self, message: Message) -> bytes:
        if "bytes" not in message:
            await self.ws.close(status.WS_1003_UNSUPPORTED_DATA)  # pragma: nocover
            raise RuntimeError(
                "Expected bytes websocket messages, but got others"
            )  # pragma: nocover
        return message["bytes"]

    async def _decode_json(self, message: Message) -> typing.Any:
        try:
            if "text" in message:
                msg_json = json.loads(message["text"])
            elif "bytes" in message:
                msg_json = json.loads(message["bytes"].decode("utf-8"))
        except json.JSONDecodeError:
            await self.ws.close(code=status.WS_1003_UNSUPPORTED_DATA)
            raise RuntimeError("Malformed JSON data received.")
        else:
            return msg_json

    async def _decode_unknown(self, message: Message) -> str:
        return await self._decode_text(message)  # pragma: nocover

    async def _decode_none(self, message: Message) -> str:
        return await self._decode_text(message)  # pragma: nocover

    async def on_connect(self, **kwargs: typing.Any) -> None:
        """Override to handle an incoming websocket connection"""
        await self.ws.accept()

    async def on_receive(self, data: typing.Any) -> typing.Any:
        """Override to handle an incoming websocket message"""
        pass  # pragma: no cover

    async def on_disconnect(self, code: int) -> None:
        """Override to handle a disconnecting websocket"""
        pass  # pragma: no cover
