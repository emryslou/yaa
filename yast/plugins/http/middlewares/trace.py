import logging

from yast.datastructures import MutableHeaders
from yast.middlewares.core import Middleware
from yast.types import ASGIApp, Message, Receive, Scope, Send

trace_log = logging.getLogger("yast.trace")


class TraceMiddleware(Middleware):
    def __init__(self, app: ASGIApp, log_config: dict = {}) -> None:
        super().__init__(app)
        if log_config:
            pass

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
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
                    headers.append(_x_trace_header, _x_trace_value)
                await send(message)

        else:
            sender = send

        if _x_trace_value is None:
            _x_trace_value = str(uuid.uuid4())
        scope["trace_id"] = _x_trace_value

        await self.app(scope, receive, sender)
