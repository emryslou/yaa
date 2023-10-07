import asyncio
import typing

import yast.status as status
from yast.concurrency import run_in_threadpool
from yast.exceptions import HttpException
from yast.requests import Request
from yast.responses import PlainTextResponse
from yast.types import Message, Receive, Scope, Send
from yast.websockets import WebSocket

try:
    import ujson as json
except ImportError:  # pragma: no cover
    import json  # pragma: no cover


class _Endpoint(object):
    _type = ""

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == self._type
        self._scope = scope
        self._receive = receive
        self._send = send

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    async def dispatch(self) -> None:
        raise NotImplementedError()  # pragma: no cover


class HttpEndPoint(_Endpoint):
    _type = "http"

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        super().__init__(scope, receive, send)

    async def dispatch(self) -> None:
        req = Request(self._scope, receive=self._receive)

        handler_name = "get" if req.method == "HEAD" else req.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        if asyncio.iscoroutinefunction(handler):
            res = await handler(req)
        else:
            res = await run_in_threadpool(handler, req)

        await res(self._scope, self._receive, self._send)

    async def method_not_allowed(self, req: Request):
        if "app" in self._scope:
            raise HttpException(status_code=405)  # pragma: nocover
        return PlainTextResponse("Method Not Allowed", 405)


class WebSocketEndpoint(_Endpoint):
    _type = "websocket"
    encoding = None  # 'text', 'bytes', 'json'
    ws: WebSocket = None

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
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
                    close_code = message.get("code", status.WS_1000_NORMAL_CLOSURE)
                    break
        except Exception as exc:  # pragma: nocover
            close_code = status.WS_1011_INTERNAL_ERROR  # pragma: nocover
            raise exc  # pragma: nocover
        finally:
            await self.on_disconnect(close_code)

    async def send(self, data, send_type: str = "bytes"):
        fn = getattr(self.ws, "send_" + send_type)
        await fn(data)

    async def decode(self, message: Message):
        if self.encoding is not None:
            decode_fn_name = "_decode_" + self.encoding.lower()
            if not hasattr(self, decode_fn_name):
                decode_fn_name = "_decode_unknown"  # pragma: nocover
        else:
            decode_fn_name = "_decode_none"  # pragma: nocover

        decode_fn = getattr(self, decode_fn_name)
        return await decode_fn(message)

    async def _decode_text(self, message: Message):
        if "text" not in message:
            await self.ws.close(status.WS_1003_UNSUPPORTED_DATA)  # pragma: nocover
            raise RuntimeError(
                "Expected text websocket messages, but got others"
            )  # pragma: nocover
        return message["text"]

    async def _decode_bytes(self, message: Message):
        if "bytes" not in message:
            await self.ws.close(status.WS_1003_UNSUPPORTED_DATA)  # pragma: nocover
            raise RuntimeError(
                "Expected bytes websocket messages, but got others"
            )  # pragma: nocover
        return message["bytes"]

    async def _decode_json(self, message: Message):
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

    async def _decode_unknown(self, message: Message):
        return await self._decode_text(message)  # pragma: nocover

    async def _decode_none(self, message: Message):
        return await self._decode_text(message)  # pragma: nocover

    async def on_connect(self, **kwargs: typing.Any) -> None:
        """Override to handle an incoming websocket connection"""
        await self.ws.accept()

    async def on_receive(self, data):
        """Override to handle an incoming websocket message"""
        pass  # pragma: no cover

    async def on_disconnect(self, code: int):
        """Override to handle a disconnecting websocket"""
        pass  # pragma: no cover
