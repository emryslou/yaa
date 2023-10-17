import gzip
import io

from yaa.datastructures import Headers, MutableHeaders
from yaa.middlewares import Middleware
from yaa.types import ASGI3App, Message, Receive, Scope, Send


class GZipMiddleware(Middleware):
    def __init__(
        self,
        app: ASGI3App,
        debug: bool = False,
        minimum_size: int = 500,
        compresslevel: int = 9,
    ) -> None:
        super().__init__(app)
        self.debug = debug
        self.minimum_size = minimum_size
        self.compresslevel = compresslevel

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # type: ignore
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            if "gzip" in (headers.get("Accept-Encoding", "") or ""):
                res = GZipResponder(self.app, self.minimum_size, self.compresslevel)
                await res(scope, receive, send)
                return
        await self.app(scope, receive, send)


class GZipResponder(object):
    def __init__(
        self, app: ASGI3App, minimum_size: int, compresslevel: int = 9
    ) -> None:
        self.inner = app
        self.minimum_size = minimum_size
        self.send: Send = unattached_send
        self.init_message: Message = {}
        self.started = False
        self.content_encoding_set = False
        self.gzip_buffer = io.BytesIO()
        self.gzip_file = gzip.GzipFile(
            mode="wb", fileobj=self.gzip_buffer, compresslevel=compresslevel
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.send = send
        await self.inner(scope, receive, self._send)

    async def _send(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.init_message = message

            headers = Headers(raw=self.init_message["headers"])
            self.content_encoding_set = "content-encoding" in headers
        elif message["type"] == "http.response.body" and self.content_encoding_set:
            if not self.started:
                self.started = True
                await self.send(self.init_message)

            await self.send(message)
        elif message["type"] == "http.response.body" and not self.started:
            self.started = True
            body = message.get("body", b"")
            more_body = message.get("more_body", False)
            if len(body) < self.minimum_size and not more_body:
                pass
            elif not more_body:
                self.gzip_file.write(body)
                self.gzip_file.close()

                body = self.gzip_buffer.getbuffer()

                headers = MutableHeaders(raw=self.init_message["headers"])
                headers["Content-Encoding"] = "gzip"
                headers["Content-Length"] = str(len(body))
                headers.add_vary_header("Accept-Encoding")

                message["body"] = body  # type: ignore[index]
            else:
                headers = MutableHeaders(raw=self.init_message["headers"])
                headers["Content-Encoding"] = "gzip"
                headers.add_vary_header("Accept-Encoding")
                del headers["Content-Length"]

                self.gzip_file.write(body)

                message["body"] = self.gzip_buffer.getvalue()  # type: ignore[index]

                self.gzip_buffer.seek(0)
                self.gzip_buffer.truncate()
            # endif

            await self.send(self.init_message)

            await self.send(message)
        elif message["type"] == "http.response.body":
            body = message.get("body", b"")
            more_body = message.get("more_body", False)

            self.gzip_file.write(body)
            if not more_body:
                self.gzip_file.close()

            message["body"] = self.gzip_buffer.getvalue()  # type: ignore[index]

            self.gzip_buffer.seek(0)
            self.gzip_buffer.truncate()

            await self.send(message)
        # end if


async def unattached_send(_: Message) -> None:
    raise RuntimeError("send awaitable not set")  # pragma: nocover
