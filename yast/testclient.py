import asyncio
import http
import inspect
import io
import json
import queue
import threading
import types
import typing
from urllib.parse import unquote, urljoin, urlsplit

import requests

from yast.plugins.lifespan.types import EventType as LifespanET
from yast.types import Receive, Scope, Send
from yast.websockets import WebSocketDisconnect

ASGIInstance = typing.Callable[[Receive, Send], typing.Awaitable[None]]
ASGI2App = typing.Callable[[Scope], ASGIInstance]
ASGI3App = typing.Callable[[Scope, Receive, Send], typing.Awaitable[None]]


class _HeaderDict(requests.packages.urllib3._collections.HTTPHeaderDict):
    def get_all(self, key, default):
        return self.getheaders(key)


class _MockOriginalResponse(object):
    """
    We have to jump through some hoops to present the response as if
    it was made using urllib3.
    """

    def __init__(self, headers):
        self.msg = _HeaderDict(headers)
        self.closed = False

    def isclosed(self):
        return self.closed


class _Upgrade(Exception):
    def __init__(self, session):
        self.session = session


def _get_reason_phrase(status_code):
    try:
        return http.HTTPStatus(status_code).phrase
    except ValueError:
        return ""


def _is_asgi3(app: typing.Union[ASGI2App, ASGI3App]) -> bool:
    if inspect.isclass(app):
        if hasattr(app, "__await__"):
            return True
    elif inspect.isfunction(app):
        return asyncio.iscoroutinefunction(app)

    call = getattr(app, "__call__", None)
    return asyncio.iscoroutinefunction(call)


class _WrapASGI2:
    """
    Provide an ASGI3 interface onto an ASGI2 app.
    """

    def __init__(self, app: ASGI2App) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope)(receive, send)


class _ASGIAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, app: ASGI3App, raise_server_exceptions=True) -> None:
        self.app = app
        self.raise_server_exceptions = raise_server_exceptions

    def send(self, request, *args, **kwargs):
        scheme, netloc, path, query, fragement = urlsplit(request.url)

        default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[scheme]

        if ":" in netloc:
            host, port = netloc.split(":", 1)
            port = int(port)
        else:
            host = netloc
            port = default_port

        # Include the 'host' header.
        if "host" in request.headers:
            headers = []
        elif port == default_port:
            headers = [[b"host", host.encode()]]
        else:
            headers = [[b"host", (f"{host}:{port}").encode()]]

        # Include other request headers.
        headers += [
            [key.lower().encode(), value.encode()]
            for key, value in request.headers.items()
        ]

        if scheme in {"ws", "wss"}:
            subprotocol = request.headers.get("sec-websocket-protocol", None)

            if subprotocol is None:
                subprotocols = []
            else:
                subprotocols = [val.strip() for val in subprotocol.split(",")]

            scope = {
                "type": "websocket",
                "path": unquote(path),
                "root_path": "",
                "scheme": scheme,
                "query_string": query.encode(),
                "headers": headers,
                "client": ["testclient", 50000],
                "server": [host, port],
                "subprotocols": subprotocols,
            }
            session = WebSocketTestSession(self.app, scope)
            raise _Upgrade(session)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": request.method,
            "path": unquote(path),
            "root_path": "",
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": ["testclient", 50000],
            "server": [host, port],
            "extensions": {"http.response.template": {}},
        }

        async def receive():
            nonlocal request_complete, response_complete
            if request_complete:
                while not response_complete:
                    await asyncio.sleep(0.0001)
                return {"type": "http.disconnect"}

            body = request.body
            if isinstance(body, str):
                body_bytes = body.encode("utf-8")  # type: bytes
            elif body is None:
                body_bytes = b""
            elif isinstance(body, types.GeneratorType):
                try:
                    chunk = body.send(None)
                    if isinstance(chunk, str):
                        chunk = chunk.encode("utf-8")
                    return {"type": "http.request", "body": chunk, "more_body": True}
                except StopIteration:
                    request_complete = True
                    return {
                        "type": "http.request",
                        "body": b"",
                    }
            else:
                body_bytes = body

            request_complete = True
            return {"type": "http.request", "body": body_bytes}

        async def send(message):
            nonlocal raw_kwargs, response_started, response_complete
            nonlocal template, context
            if message["type"] == "http.response.start":
                assert (
                    not response_started
                ), 'Received multiple "http.response.start" messages'
                raw_kwargs["version"] = 11
                raw_kwargs["status"] = message["status"]
                raw_kwargs["reason"] = _get_reason_phrase(message["status"])
                raw_kwargs["headers"] = [
                    (key.decode(), value.decode()) for key, value in message["headers"]
                ]
                raw_kwargs["preload_content"] = False
                raw_kwargs["original_response"] = _MockOriginalResponse(
                    raw_kwargs["headers"]
                )
                response_started = True
            elif message["type"] == "http.response.body":
                assert (
                    response_started
                ), 'Received "http.response.body" without "http.response.start".'
                assert (
                    not response_complete
                ), 'Received "http.response.body" after response completed'
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if request.method != "HEAD":
                    raw_kwargs["body"].write(body)

                if not more_body:
                    raw_kwargs["body"].seek(0)
                    response_complete = True
            elif message["type"] == "http.response.template":
                template = message["template"]
                context = message["context"]

        request_complete = False
        response_started = False
        response_complete = False
        raw_kwargs = {"body": io.BytesIO()}
        template = None
        context = None

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.app(scope, receive, send))
        except BaseException as exc:
            if self.raise_server_exceptions:
                raise exc from None

        if self.raise_server_exceptions:
            assert response_started, "TestClient did not receive any response"
        elif not response_started:
            raw_kwargs = {
                "version": 11,
                "status": 500,
                "reason": "Internal Server Error",
                "headers": [],
                "preload_content": False,
                "original_response": _MockOriginalResponse([]),
                "body": io.BytesIO(),
            }

        raw = requests.packages.urllib3.HTTPResponse(**raw_kwargs)
        res = self.build_response(request, raw)
        if template is not None:
            res.template = template
            res.context = context
        return res


class WebSocketTestSession(object):
    def __init__(self, app: ASGI3App, scope: Scope):
        self.app = app
        self.scope = scope
        self.accepted_subprotocol = None
        self._loop = asyncio.new_event_loop()
        self._receive_queue = queue.Queue()
        self._send_queue = queue.Queue()
        self._thread = threading.Thread(target=self._run)
        self.send({"type": "websocket.connect"})
        self._thread.start()

        message = self.receive()
        self._raise_on_close(message)
        self.accepted_subprotocol = message.get("subprotocol", None)

    def __enter__(self) -> "WebSocketTestSession":
        return self

    def __exit__(self, *args):
        self.close(1000)
        self._thread.join()
        while not self._send_queue.empty():
            message = self.receive()
            if isinstance(message, BaseException):
                raise message  # pragma: nocover

    def _run(self):
        scope = self.scope
        receive = self._asgi_receive
        send = self._asgi_send
        try:
            self._loop.run_until_complete(self.app(scope, receive, send))
        except BaseException as exc:
            self.__sput(exc)

    async def _asgi_receive(self):
        while self._receive_queue.empty():
            await asyncio.sleep(0)
        return self._receive_queue.get()

    async def _asgi_send(self, message):
        self.__sput(message)

    def _raise_on_close(self, message):
        if message["type"] == "websocket.close":
            raise WebSocketDisconnect(message.get("code", 1000))

    def send(self, value):
        if value is None:
            raise RuntimeError("value is None")  # pragma: nocover
        self._receive_queue.put(value)

    def send_text(self, data: str):
        self.send({"type": "websocket.receive", "text": data})

    def send_bytes(self, data: bytes):
        self.send({"type": "websocket.receive", "bytes": data})

    def send_json(self, data):
        _j = json.dumps(data).encode("utf-8")
        self.send_bytes(_j)

    def close(self, code=1000):
        self.send({"type": "websocket.disconnect", "code": code})

    def receive(self):
        message = self._send_queue.get()
        if isinstance(message, BaseException):
            raise message
        return message

    def receive_text(self):
        message = self.receive()
        self._raise_on_close(message)
        return message["text"]

    def receive_bytes(self) -> bytes:
        message = self.receive()
        self._raise_on_close(message)
        return message["bytes"]

    def receive_json(self):
        return json.loads(self.receive_bytes().decode("utf-8"))

    def __sput(self, message):
        if message is None:
            raise RuntimeError("value is None")  # pragma: nocover
        self._send_queue.put(message)


class TestClient(requests.Session):
    __test__ = False

    def __init__(
        self,
        app: typing.Union[ASGI2App, ASGI3App],
        base_url: str = "http://testserver",
        raise_server_exceptions=True,
    ) -> None:
        super().__init__()
        if _is_asgi3(app):
            app = typing.cast(ASGI3App, app)
            asgi_app = app
        else:
            app = typing.cast(ASGI2App, app)
            asgi_app = _WrapASGI2(app)

        adapter = _ASGIAdapter(asgi_app, raise_server_exceptions)
        self.mount("http://", adapter)
        self.mount("https://", adapter)
        self.mount("ws://", adapter)
        self.mount("wss://", adapter)
        self.headers.update({"user-agent": "testclient"})
        self.base_url = base_url
        self.app = asgi_app

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        url = urljoin(self.base_url, url)
        return super().request(method, url, **kwargs)

    def wsconnect(self, url: str, subprotocols=None, **kwargs) -> WebSocketTestSession:
        url = urljoin("ws://testserver", url)
        headers = kwargs.get("headers", {})
        headers.setdefault("connection", "upgrade")
        headers.setdefault("sec-websocket-key", "testserver==")
        headers.setdefault("sec-websocket-version", "13")
        if subprotocols is not None:
            headers.setdefault("sec-websocket-protocol", ",".join(subprotocols))

        kwargs["headers"] = headers

        try:
            self.request("GET", url, **kwargs)
        except _Upgrade as exc:
            return exc.session
        else:
            raise RuntimeError("Expected WebSocket upgrade")  # pragma: no cover

    def __enter__(self) -> requests.Session:
        loop = asyncio.get_event_loop()
        self.send_queue = asyncio.Queue()
        self.receive_queue = asyncio.Queue()

        self.task = loop.create_task(self.lifespan())
        loop.run_until_complete(self.wait_et("startup"))
        return self

    def __exit__(self, *args: typing.Any) -> None:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.wait_et("shutdown"))

    async def lifespan(self) -> None:
        try:
            await self.app(
                {"type": "lifespan"}, self.receive_queue.get, self.send_queue.put
            )
        finally:
            await self.send_queue.put(None)

    async def wait_et(self, event_type: str) -> None:
        event_type = LifespanET(event_type)
        await self.receive_queue.put({"type": event_type.lifespan})
        message = await self.send_queue.get()
        if message is None:
            self.task.result()
        assert message["type"] == event_type.complete

        if event_type == LifespanET.SHUTDOWN:
            await self.task
