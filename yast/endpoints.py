import asyncio
import typing

import ujson as json

import yast.status as status
from yast.concurrency import run_in_threadpool
from yast.exceptions import HttpException
from yast.requests import Request
from yast.responses import PlainTextResponse, Response
from yast.types import Message, Receive, Scope, Send
from yast.websockets import WebSocket


class HttpEndPoint(object):
    def __init__(self, scope: Scope) -> None:
        assert scope["type"] == "http"
        self.scope = scope

    async def __call__(self, receive: Receive, send: Send) -> None:
        req = Request(self.scope, receive)
        res = await self.dispatch(req)

        await res(receive, send)

    async def dispatch(self, req: Request) -> Response:
        handler_name = "get" if req.method == "HEAD" else req.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        if asyncio.iscoroutinefunction(handler):
            res = await handler(req)
        else:
            res = await run_in_threadpool(handler, req)
        return res

    async def method_not_allowed(self, req: Request):
        if "app" in self.scope:
            raise HttpException(status_code=405)  # pragma: nocover
        return PlainTextResponse("Method Not Allowed", 405)


class WebSocketEndpoint(object):
    encoding = None  # 'text', 'bytes', 'json'
    ws: WebSocket = None

    def __init__(self, scope: Scope) -> None:
        assert scope["type"] == "websocket"
        self.scope = scope

    async def __call__(self, receive: Receive, send: Send) -> None:
        self.ws = WebSocket(self.scope, receive, send)
        kwargs = self.scope.get("kwargs", {})
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
            raise exc from None  # pragma: nocover
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
        except json.decoder.JSONDecodeError:
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
