import io
import math
import sys
import typing

import anyio

from yaa.types import ASGI3App, Receive, Scope, Send

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
    def __init__(self, app: ASGI3App) -> None:
        super().__init__(app)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"
        await WSGIResponser(self.app)(scope, receive, send)


class WSGIResponser(object):
    def __init__(self, app: ASGI3App) -> None:
        self.app = app
        self.status = None
        self.response_headers = None
        self.stream_send, self.stream_receive = anyio.create_memory_object_stream(
            math.inf
        )
        self.response_started = False
        self.exc_info = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        environ = build_environ(scope, body)
        async with anyio.create_task_group() as tg:
            tg.start_soon(self.sender, send)
            async with self.stream_send:
                await anyio.to_thread.run_sync(self.wsgi, environ, self.start_response)

        if self.exc_info is not None:
            raise self.exc_info[0].with_traceback(self.exc_info[1], self.exc_info[2])

    async def sender(self, send: Send) -> None:
        async with self.stream_receive:
            async for message in self.stream_receive:
                await send(message)

    def start_response(
        self,
        status: str,
        response_headers: typing.List[typing.Tuple[str, str]],
        exc_info: typing.Optional[typing.Any] = None,
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

            anyio.from_thread.run(
                self.stream_send.send,
                {
                    "type": "http.response.start",
                    "status": status_code,
                    "headers": headers,
                },
            )

    def wsgi(self, environ: dict, start_response: typing.Callable) -> None:
        for chunk in self.app(environ, start_response):  # type: ignore
            anyio.from_thread.run(
                self.stream_send.send,
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                },
            )

        anyio.from_thread.run(
            self.stream_send.send, {"type": "http.response.body", "body": b""}
        )
