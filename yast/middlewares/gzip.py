import gzip
import io

from yast.datastructures import Headers, MutableHeaders
from yast.types import ASGIApp, ASGIInstance, Message, Receive, Scope, Send


class GZipMiddleware(object):
    def __init__(self, app: ASGIApp, minimum_size: int = 500) -> None:
        self.app = app
        self.minimum_size = minimum_size

    def __call__(self, scope: Scope) -> ASGIInstance:
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            if "gzip" in headers.get("Accept-Encoding", ""):
                return GZipResponder(self.app, scope, self.minimum_size)
        return self.app(scope)


class GZipResponder(object):
    def __init__(self, app: ASGIApp, scope: Scope, minimum_size: int) -> None:
        self.inner = app(scope)
        self.minimum_size = minimum_size
        self.send = unattached_send
        self.init_message = {}
        self.started = False
        self.gzip_buffer = io.BytesIO()
        self.gzip_file = gzip.GzipFile(mode="wb", fileobj=self.gzip_buffer)

    async def __call__(self, receive: Receive, send: Send) -> None:
        self.send = send
        await self.inner(receive, self._send)

    async def _send(self, message: Message):
        if message["type"] == "http.response.start":
            self.init_message = message
        elif message["type"] == "http.response.body":
            if not self.started:
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
                    message["body"] = body
                else:
                    headers = MutableHeaders(raw=self.init_message["headers"])
                    headers["Content-Encoding"] = "gzip"
                    headers.add_vary_header("Accept-Encoding")
                    del headers["Content-Length"]
                    self.gzip_file.write(body)
                    message["body"] = self.gzip_buffer.getvalue()
                    self.gzip_buffer.seek(0)
                    self.gzip_buffer.truncate()
                # endif

                await self.send(self.init_message)
                await self.send(message)
            else:
                body = message.get("body", b"")
                more_body = message.get("more_body", False)

                self.gzip_file.write(body)
                if not more_body:
                    self.gzip_file.close()
                message["body"] = self.gzip_buffer.getvalue()
                self.gzip_buffer.seek(0)
                self.gzip_buffer.truncate()
                await self.send(message)


async def unattached_send(_):
    raise RuntimeError("send awaitable not set")  # pragma: nocover
