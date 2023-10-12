import logging

from yaa.datastructures import MutableHeaders
from yaa.middlewares.core import Middleware
from yaa.types import ASGI3App, Message, Receive, Scope, Send

trace_log = logging.getLogger("yaa.trace")


class TraceMiddleware(Middleware):
    def __init__(
        self, app: ASGI3App, log_config: dict = {}, debug: bool = False
    ) -> None:
        super().__init__(app)
        self.debug = debug
        if log_config:
            pass  # pragma: no cover

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # type: ignore
        import uuid

        _x_trace_header = "X-Trace-Id"
        _x_trace_value = None

        if scope["type"] in ("websocket", "http"):
            for name, value in scope["headers"]:
                if _x_trace_header.lower() == name.decode().lower():
                    _x_trace_value = value.decode()
                    break

            async def sender(message: Message) -> None:
                if message["type"] == "http.response.start":
                    headers = MutableHeaders(scope=message)
                    headers.append(_x_trace_header, _x_trace_value)  # type: ignore
                await send(message)

        else:
            sender = send  # type: ignore  # pragma: no cover

        if _x_trace_value is None:
            _x_trace_value = str(uuid.uuid4())
        scope["trace_id"] = _x_trace_value  # type: ignore

        await self.app(scope, receive, sender)
