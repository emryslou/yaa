import enum
import json
import typing

from yaa.requests import HttpConnection
from yaa.types import Message, Receive, Scope, Send


class WebSocketState(enum.Enum):
    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2


class WebSocketDisconnect(Exception):
    def __init__(self, code=1000):
        self.code = code


class WebSocket(HttpConnection):
    def __init__(
        self, scope: Scope, receive: Receive = None, send: Send = None
    ) -> None:
        assert scope["type"] == "websocket"
        self._scope = scope
        self._receive = receive
        self._send = send
        self.client_state = WebSocketState.CONNECTING
        self.application_state = WebSocketState.CONNECTING

    async def receive(self) -> Message:
        if self.client_state == WebSocketState.CONNECTING:
            message = await self._receive()
            assert message["type"] == "websocket.connect"
            self.client_state = WebSocketState.CONNECTED
            return message
        elif self.client_state == WebSocketState.CONNECTED:
            message = await self._receive()
            assert message["type"] in {"websocket.receive", "websocket.disconnect"}
            if message["type"] == "websocket.disconnect":
                self.client_state = WebSocketState.DISCONNECTED
            return message
        else:
            raise RuntimeError(
                'Cannot call "receive" once a disconnect message has been received'
            )

    async def send(self, message: Message) -> None:
        if self.application_state == WebSocketState.CONNECTING:
            assert message["type"] in {"websocket.accept", "websocket.close"}

            if message["type"] == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED
            else:
                self.application_state = WebSocketState.CONNECTED
            await self._send(message)
        elif self.application_state == WebSocketState.CONNECTED:
            assert message["type"] in {"websocket.send", "websocket.close"}

            if message["type"] == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED

            await self._send(message)
        else:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')

    async def accept(
        self, subprotocol: str = None,
        headers: typing.Iterator[typing.Tuple[bytes, bytes]] = None
    ) -> None:
        if self.client_state == WebSocketState.CONNECTING:
            await self.receive()
        await self.send({
            "type": "websocket.accept", "subprotocol": subprotocol,
            'headers': headers,
        })

    def _raise_on_disconnect(self, message: Message):
        if message is None:
            raise RuntimeError("Message is None")  # pragma: nocover
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message["code"])

    async def receive_text(self) -> str:
        assert self.application_state == WebSocketState.CONNECTED

        message = await self.receive()
        self._raise_on_disconnect(message)
        return message["text"]

    async def receive_bytes(self) -> bytes:
        assert self.application_state == WebSocketState.CONNECTED

        message = await self.receive()
        self._raise_on_disconnect(message)
        return message["bytes"]

    async def receive_json(self) -> typing.Any:
        json_bytes = await self.receive_bytes()
        return json.loads(json_bytes.decode("utf-8"))

    async def iter_text(self) -> typing.AsyncIterator[str]:
        try:
            while True:
                yield await self.receive_text()
        except WebSocketDisconnect:
            pass

    async def iter_bytes(self) -> typing.AsyncIterator[bytes]:
        try:
            while True:
                yield await self.receive_bytes()
        except WebSocketDisconnect:
            pass

    async def iter_json(self) -> typing.AsyncIterator[typing.Any]:
        try:
            while True:
                yield await self.receive_json()
        except WebSocketDisconnect:
            pass

    async def send_text(self, data: str) -> None:
        await self.send({"type": "websocket.send", "text": data})

    async def send_bytes(self, data: bytes) -> None:
        await self.send({"type": "websocket.send", "bytes": data})

    async def send_json(self, data) -> None:
        _j = json.dumps(data).encode("utf-8")
        await self.send({"type": "websocket.send", "bytes": _j})

    async def close(self, code=1000) -> None:
        await self.send({"type": "websocket.close", "code": code})


class WebSocketClose(object):
    def __init__(self, code: int = 1000):
        self.code = code

    async def __call__(self, receive: Receive, send: Send) -> None:
        await send({"type": "websocket.close", "code": self.code})
