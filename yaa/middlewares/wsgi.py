import asyncio
import io
import sys
import typing

from yaa.concurrency import run_in_threadpool
from yaa.types import ASGIApp, Receive, Scope, Send

from .core import Middleware


def build_environ(scope: Scope, body: bytes) -> dict:
    environ = {
        "REQUEST_METHOD": scope["method"],
        "SCRIPT_NAME": scope.get("root_path", "").encode("utf8").decode("latin1"),
        "PATH_INFO": scope.get("path", "").encode("utf8").decode("latin1"),
        "QUERY_STRING": scope["query_string"].decode("ascii"),
        "SERVER_PROTOCOL": "HTTP/%s" % scope["http_version"],
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": scope.get("scheme", "http"),
        "wsgi.input": io.BytesIO(body),
        "wsgi.errors": sys.stdout,
        "wsgi.multithread": True,
        "wsgi.multiprocess": True,
        "wsgi.run_once": False,
    }

    server = scope.get("server") or ("localhost", 80)
    environ["SERVER_NAME"] = server[0]
    environ["SERVER_PORT"] = server[1]

    if scope.get("client"):
        environ["REMOTE_ADDR"] = scope["client"][0]

    for name, value in scope.get("headers", []):
        name = name.decode("latin-1")
        if name == "content-length":
            corrected_name = "CONTENT_LENGTH"
        elif name == "content-type":
            corrected_name = "CONTENT_TYPE"
        else:
            corrected_name = "HTTP_%s" % name.upper().replace("-", "_")

        value = value.decode("latin-1")
        if corrected_name in environ:
            value = environ[corrected_name] + "," + value

        environ[corrected_name] = value

    return environ


class WSGIMiddleware(Middleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"
        await WSGIResponser(self.app)(scope, receive, send)


class WSGIResponser(object):
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.status = None
        self.response_headers = None
        self.send_event = asyncio.Event()
        self.send_queue = []
        self.loop = asyncio.get_event_loop()
        self.response_started = False
        self.exc_info = None
        self._running = True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        environ = build_environ(scope, body)
        sender = None
        try:
            wsgi = run_in_threadpool(self.wsgi, environ, self.start_response)

            sender = self.loop.create_task(self.sender(send))
            await asyncio.wait_for(wsgi, None)

            self.send_queue.append(None)
            self.send_event.set()
            await asyncio.wait_for(sender, None)

            if self.exc_info is not None:
                raise self.exc_info[0].with_traceback(
                    self.exc_info[1], self.exc_info[2]
                )
        finally:
            if not sender.done():
                sender.cancel()

    async def sender(self, send: Send) -> None:
        while True:
            try:
                if self.send_queue:
                    message = self.send_queue.pop(0)
                    if message is None:
                        return
                    await send(message)
                else:
                    await self.send_event.wait()
                    self.send_event.clear()
            except asyncio.CancelledError as exc:
                raise exc  # pragma: nocover

    def start_response(
        self,
        status: str,
        response_headers: typing.List[typing.Tuple[str, str]],
        exc_info=None,
    ) -> None:
        self.exc_info = exc_info
        if not self.response_started:
            self.response_started = True
            status_code_str, _ = status.split(" ", 1)
            status_code = int(status_code_str)
            headers = [
                (name.strip().encode("ascii"), value.encode("ascii"))
                for name, value in response_headers
            ]

            self.send_queue.append(
                {
                    "type": "http.response.start",
                    "status": status_code,
                    "headers": headers,
                }
            )
            self.loop.call_soon_threadsafe(self.send_event.set)

    def wsgi(self, environ: dict, start_response: typing.Callable) -> None:
        for chunk in self.app(environ, start_response):
            self.send_queue.append(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                }
            )
            self.loop.call_soon_threadsafe(self.send_event.set)

        self.send_queue.append({"type": "http.response.body", "body": b""})
        self.loop.call_soon_threadsafe(self.send_event.set)
