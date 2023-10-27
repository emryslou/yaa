import enum
import json
import typing
import warnings

import anyio

from yaa.requests import HttpConnection
from yaa.types import Message, Receive, Scope, Send


class WebSocketState(enum.Enum):
    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2


class WebSocketDisconnect(Exception):
    def __init__(self, code: int = 1000, reason: typing.Optional[str] = None) -> None:
        self.code = code
        self.reason = reason or ""


class WebSocketAgent(object):
    def __init__(self) -> None:
        self.active_connections: typing.Mapping[str, "WebSocket"] = {}

    def connect(self, websocket: "WebSocket") -> None:
        self.active_connections[websocket.quid] = websocket  # type: ignore[index]

    def disconnect(self, websocket: "WebSocket") -> None:
        if websocket.quid in self.active_connections:
            del self.active_connections[websocket.quid]  # type: ignore[attr-defined]

    async def send_to(
        self, ws_quid: str, send_fn: str, **send_kwargs: typing.Any
    ) -> None:
        try:
            ws = self.active_connections[ws_quid]
            await getattr(ws, send_fn)(**send_kwargs)
        except KeyError as exc:  # pragma: no cover
            warnings.warn(
                f"send error, {ws_quid!r} may offline, msg: {exc}"
            )  # pragma: no cover

    async def broadcast(self, send_fn: str, **send_kwargs: typing.Any) -> None:
        try:
            for _, ws in self.active_connections.items():
                await getattr(ws, send_fn)(**send_kwargs)
        except BaseException as exc:  # pragma: no cover
            warnings.warn(
                f"some error happens, but we ignore it, msg: {exc}"
            )  # pragma: no cover

    async def broadcast_skip(
        self, skip_quids: list, send_fn: str, **send_kwargs: typing.Any
    ) -> None:
        try:
            for _quid, ws in self.active_connections.items():
                if len(skip_quids) > 0 and _quid in skip_quids:
                    continue
                await getattr(ws, send_fn)(**send_kwargs)
        except BaseException as exc:  # pragma: no cover
            warnings.warn(
                f"some error happens, but we ignore it, msg: {exc}"
            )  # pragma: no cover


class WebSocket(HttpConnection):
    def __init__(
        self,
        scope: Scope,
        receive: typing.Optional[Receive] = None,
        send: typing.Optional[Send] = None,
    ) -> None:
        assert scope["type"] == "websocket"

        self._quid = None
        self._scope = scope
        if "quid" in scope:
            self._quid = scope["quid"]

        self._receive = receive
        self._send = send
        self.client_state = WebSocketState.CONNECTING
        self.application_state = WebSocketState.CONNECTING
        if "app" in self._scope:
            self._agent = self._scope["app"].websocket_agent  # type: WebSocketAgent
            self._agent.connect(self)

    async def receive(self) -> Message:
        if self.client_state == WebSocketState.CONNECTING:
            message = await self._receive()  # type: ignore
            if message["type"] != "websocket.connect":
                raise RuntimeError(
                    "Expected ASGI message `websocket.connect`, "
                    f'but got `{message["type"]!r}`'
                )
            self.client_state = WebSocketState.CONNECTED
            return message
        elif self.client_state == WebSocketState.CONNECTED:
            message = await self._receive()  # type: ignore
            if message["type"] not in {"websocket.receive", "websocket.disconnect"}:
                raise RuntimeError(
                    "Expected ASGI message `websocket.receive` or "
                    f' `websocket.disconnect`, but got `{message["type"]!r}`'
                )

            if message["type"] == "websocket.disconnect":
                self.client_state = WebSocketState.DISCONNECTED
            return message
        else:
            raise RuntimeError(
                'Cannot call "receive" once a disconnect message has been received'
            )

    async def send(self, message: Message) -> None:
        if self.application_state == WebSocketState.CONNECTING:
            if message["type"] not in {"websocket.accept", "websocket.close"}:
                raise RuntimeError(
                    "Expected ASGI message `websocket.accept` or "
                    f' `websocket.close`, but got `{message["type"]!r}`'
                )
            if message["type"] == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED
            else:
                self.application_state = WebSocketState.CONNECTED
            await self._send(message)  # type: ignore
        elif self.application_state == WebSocketState.CONNECTED:
            if message["type"] not in {"websocket.send", "websocket.close"}:
                raise RuntimeError(
                    "Expected ASGI message `websocket.send` or "
                    f' `websocket.close`, but got `{message["type"]!r}`'
                )

            if message["type"] == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED

            await self._send(message)  # type: ignore
        else:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')

    async def accept(
        self,
        subprotocol: typing.Optional[str] = None,
        headers: typing.Optional[typing.Iterator[typing.Tuple[bytes, bytes]]] = None,
    ) -> None:
        headers = headers or []  # type: ignore
        if self.client_state == WebSocketState.CONNECTING:
            await self.receive()
        await self.send(  # type: ignore
            {
                "type": "websocket.accept",
                "subprotocol": subprotocol,
                "headers": headers,
            }
        )

    def _raise_on_disconnect(self, message: Message) -> None:
        if message["type"] == "websocket.disconnect":
            if hasattr(self, "_agent"):
                self._agent.disconnect(self)  # pragma: no cover
            raise WebSocketDisconnect(message["code"], message.get("reason", ""))

    async def receive_text(self) -> str:
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeError(
                "WebSocket is not connected. Need to call `accept` first "
            )

        message = await self.receive()
        self._raise_on_disconnect(message)
        return message["text"]

    async def receive_bytes(self) -> bytes:
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeError(
                "WebSocket is not connected. Need to call `accept` first "
            )

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

    async def send_json(self, data: typing.Any) -> None:
        _j = json.dumps(data).encode("utf-8")
        await self.send({"type": "websocket.send", "bytes": _j})

    async def close(
        self, code: int = 1000, reason: typing.Optional[str] = None
    ) -> None:
        if hasattr(self, "_agent"):
            self._agent.disconnect(self)
        await self.send(
            {"type": "websocket.close", "code": code, "reason": reason or ""}
        )

    async def broadcast(self, message):
        if hasattr(self, "_agent"):
            await self._agent.broadcast("send_text", data=message)

    async def notify_others(self, message):
        if hasattr(self, "_agent"):
            await self._agent.broadcast_skip([self.quid], "send_text", data=message)

    @property
    def quid(self) -> str:
        if self._quid is None:
            import uuid

            self._quid = f"ws-{uuid.uuid4()}"

        return self._quid


class WebSocketClose(object):
    def __init__(self, code: int = 1000, reason: typing.Optional[str] = None) -> None:
        self.code = code
        self.reason = reason or ""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {"type": "websocket.close", "code": self.code, "reason": self.reason}
        )
