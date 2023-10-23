import anyio, pytest, typing
from contextlib import AsyncExitStack

from yaa.applications import Yaa
from yaa.background import BackgroundTask
from yaa.middlewares import Middleware, BaseHttpMiddleware
from yaa.responses import Response, PlainTextResponse, StreamingResponse
from yaa.routing import Route
from yaa.types import Scope, Receive, Send
from yaa._utils import get_logger

logger = get_logger(__name__)


class CustomMiddleware(BaseHttpMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Custom-Header"] = "Example"
        return response


app = Yaa()
app.add_middleware(CustomMiddleware)


@app.route("/")
def homepage(request):
    return PlainTextResponse("Homepage")


@app.route("/exc")
def exc(request):
    raise Exception("Exc")


@app.route("/no-response")
class NoResponse:
    def __init__(self, scope, receive, send):
        pass

    def __await__(self):
        return self.dispatch().__await__()

    async def dispatch(self):
        pass


@app.ws_route("/ws")
async def websocket_endpoint(session):
    await session.accept()
    await session.send_text("Hello, world!")
    await session.close()


def test_custom_middleware(client_factory):
    client = client_factory(app)
    response = client.get("/")
    assert response.headers["Custom-Header"] == "Example"

    with pytest.raises(Exception) as ctx:
        response = client.get("/exc")
    assert str(ctx.value) == "Exc"

    with pytest.raises(RuntimeError):
        response = client.get("/no-response")

    with client.wsconnect("/ws") as session:
        text = session.receive_text()
        assert text == "Hello, world!"


def test_middleware_decorator(client_factory):
    app = Yaa()

    @app.route("/homepage")
    def homepage(request):
        return PlainTextResponse("Homepage")

    @app.middleware("http")
    async def plaintext(request, call_next):
        if request.url.path == "/":
            return PlainTextResponse("OK")
        response = await call_next(request)
        response.headers["Custom"] = "Example"
        return response

    client = client_factory(app)
    response = client.get("/")
    assert response.text == "OK"

    response = client.get("/homepage")
    assert response.text == "Homepage"
    assert response.headers["Custom"] == "Example"


def test_state_data_across_multiple_middlewares(client_factory):
    expected_value1 = "foo"
    expected_value2 = "bar"

    class aMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            request.state.foo = expected_value1
            response = await call_next(request)
            return response

    class bMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            request.state.bar = expected_value2
            response = await call_next(request)
            response.headers["X-State-Foo"] = request.state.foo
            return response

    class cMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            response.headers["X-State-Bar"] = request.state.bar
            return response

    app = Yaa()
    app.add_middleware(aMiddleware)
    app.add_middleware(bMiddleware)
    app.add_middleware(cMiddleware)

    @app.route("/")
    def homepage(request):
        return PlainTextResponse("OK")

    client = client_factory(app)
    response = client.get("/")
    assert response.text == "OK"
    assert response.headers["X-State-Foo"] == expected_value1
    assert response.headers["X-State-Bar"] == expected_value2


def test_app_middleware_argument(client_factory):
    def homepage(request):
        return PlainTextResponse("Homepage")

    app = Yaa(routes=[Route("/", homepage)], middlewares=[(CustomMiddleware, {})])

    client = client_factory(app)
    response = client.get("/")
    assert response.headers["Custom-Header"] == "Example"


def test_fully_evaluated_response(client_factory):
    class CustomMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            await call_next(request)
            return PlainTextResponse("Custom")

    app = Yaa()
    app.add_middleware(CustomMiddleware)

    client = client_factory(app)
    response = client.get("/does_not_exist")
    assert response.text == "Custom"


@app.route("/exc-stream")
def exc_stream(request):
    return StreamingResponse(_generate_faulty_stream())


def _generate_faulty_stream():
    yield b"Ok"
    raise Exception("Faulty Stream")


def test_generate_faulty_stream(client_factory):
    client = client_factory(app)
    with pytest.raises(Exception) as ctx:
        response = client.get("/exc-stream")
    assert str(ctx.value) == "Faulty Stream"


def test_exception_on_mounted_apps(client_factory):
    sub_app = Yaa(routes=[Route("/", exc)])
    app.mount("/sub", sub_app)
    client = client_factory(app, raise_server_exceptions=True)
    res = client.get("/sub/")
    assert res.status_code == 500
    assert "Server Error" in res.text


@pytest.mark.anyio
async def test_run_background_tasks_even_if_client_disconnects():
    request_body_sent = False
    response_complete = anyio.Event()
    background_task_run = anyio.Event()

    async def sleep_and_set():
        # small delay to give BaseHttpMiddleware a chance to cancel us
        # this is required to make the test fail prior to fixing the issue
        # so do not be surprised if you remove it and the test still passes
        await anyio.sleep(0.1)
        background_task_run.set()

    async def endpoint_with_background_task(_):
        return PlainTextResponse(background=BackgroundTask(sleep_and_set))

    async def passthrough(request, call_next):
        return await call_next(request)

    app = Yaa(
        middlewares=[(BaseHttpMiddleware, dict(dispatch=passthrough))],
        routes=[Route("/", endpoint_with_background_task)],
    )
    scope = {
        "type": "http",
        "version": "3",
        "method": "GET",
        "path": "/",
    }

    async def receive():
        nonlocal request_body_sent
        if not request_body_sent:
            request_body_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        # We simulate a client that disconnects immediately after receiving the response
        await response_complete.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body":
            if not message.get("more_body", False):
                response_complete.set()

    await app(scope, receive, send)
    assert background_task_run.is_set()


@pytest.mark.anyio
async def test_run_context_manager_exit_even_if_client_disconnects():
    request_body_sent = False
    response_complete = anyio.Event()
    context_manager_exited = anyio.Event()

    async def sleep_and_set():
        # small delay to give BaseHttpMiddleware a chance to cancel us
        # this is required to make the test fail prior to fixing the issue
        # so do not be surprised if you remove it and the test still passes
        await anyio.sleep(0.1)
        context_manager_exited.set()

    class ContextManagerMiddleware:
        def __init__(self, app, **kwargs):
            self.app = app

        async def __call__(self, scope, receive, send):
            async with AsyncExitStack() as stack:
                stack.push_async_callback(sleep_and_set)
                await self.app(scope, receive, send)

    async def simple_endpoint(_):
        return PlainTextResponse(background=BackgroundTask(sleep_and_set))

    async def passthrough(request, call_next):
        return await call_next(request)

    app = Yaa(
        middlewares=[
            (BaseHttpMiddleware, dict(dispatch=passthrough)),
            (ContextManagerMiddleware, {}),
        ],
        routes=[Route("/", simple_endpoint)],
    )
    scope = {
        "type": "http",
        "version": "3",
        "method": "GET",
        "path": "/",
    }

    async def receive():
        nonlocal request_body_sent
        if not request_body_sent:
            request_body_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        # We simulate a client that disconnects immediately after receiving the response
        await response_complete.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body":
            if not message.get("more_body", False):
                response_complete.set()

    await app(scope, receive, send)
    assert context_manager_exited.is_set()


def test_app_receives_http_disconnect_while_sending_if_discarded(client_factory):
    class DiscardingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            await call_next(request)
            return PlainTextResponse("Custom")

    async def downstream_app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/plain"),
                ],
            }
        )

        async with anyio.create_task_group() as task_group:

            async def cancel_on_disconnect():
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        task_group.cancel_scope.cancel()
                        break

            task_group.start_soon(cancel_on_disconnect)
            # A timeout is set for 0.1 second in order to ensure that
            # cancel_on_disconnect is scheduled by the event loop
            with anyio.move_on_after(0.1):
                while True:
                    await send(
                        {
                            "type": "http.response.body",
                            "body": b"chunk ",
                            "more_body": True,
                        }
                    )
            pytest.fail(
                "http.disconnect should have been received and canceled the scope"
            )  # pragma: no cover

    app = DiscardingMiddleware(downstream_app)
    client = client_factory(app)
    response = client.get("/does_not_exist")
    assert response.text == "Custom"


def test_app_receives_http_disconnect_after_sending_if_discarded(client_factory):
    class DiscardingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            await call_next(request)
            return PlainTextResponse("Custom")

    async def downstream_app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/plain"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"first chunk, ",
                "more_body": True,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"second chunk",
                "more_body": True,
            }
        )
        message = await receive()
        assert message["type"] == "http.disconnect"

    app = DiscardingMiddleware(downstream_app)
    client = client_factory(app)
    response = client.get("/does_not_exist")
    assert response.text == "Custom"


def test_read_request_stream_in_app_after_middleware_calls_stream(
    client_factory,
) -> None:
    async def homepage(request):
        expected = [b""]
        async for chunk in request.stream():
            logger.debug(f"diff: {chunk!r} {expected[0]!r}")
            assert chunk == expected.pop(0)
        assert expected == []
        return PlainTextResponse("Homepage")

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            expected = [b"a", b""]
            async for chunk in request.stream():
                assert chunk == expected.pop(0)
            assert expected == []
            return await call_next(request)

    app = Yaa(
        routes=[Route("/", homepage, methods=["POST"])],
        middlewares=[(ConsumingMiddleware, {})],
    )

    client = client_factory(app)

    response = client.post("/", content=b"a")
    assert response.status_code == 200


def test_read_request_stream_in_app_after_middleware_calls_body(client_factory) -> None:
    async def homepage(request):
        expected = [b"a", b""]
        async for chunk in request.stream():
            assert chunk == expected.pop(0)
        assert expected == []
        return PlainTextResponse("Homepage")

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            logger.debug(f"{self.__class__.__name__}::dispatch is calling ...")
            assert await request.body() == b"a"
            return await call_next(request)

    app = Yaa(
        routes=[Route("/", homepage, methods=["POST"])],
        middlewares=[(ConsumingMiddleware, {})],
    )
    client = client_factory(app)
    response = client.post("/", content=b"a")
    assert response.status_code == 200


def test_read_request_body_in_app_after_middleware_calls_stream(client_factory) -> None:
    async def homepage(request):
        assert await request.body() == b""
        return PlainTextResponse("Homepage")

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            expected = [b"a", b""]
            async for chunk in request.stream():
                assert chunk == expected.pop(0)
            assert expected == []
            return await call_next(request)

    app = Yaa(
        routes=[Route("/", homepage, methods=["POST"])],
        middlewares=[(ConsumingMiddleware, {})],
    )
    client = client_factory(app)
    response = client.post("/", content=b"a")
    assert response.status_code == 200


def test_read_request_body_in_app_after_middleware_calls_body(client_factory) -> None:
    async def homepage(request):
        assert await request.body() == b"a"
        return PlainTextResponse("Homepage")

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            assert await request.body() == b"a"
            return await call_next(request)

    app = Yaa(
        routes=[Route("/", homepage, methods=["POST"])],
        middlewares=[(ConsumingMiddleware, {})],
    )
    client = client_factory(app)
    response = client.post("/", content=b"a")
    assert response.status_code == 200


def test_read_request_stream_in_dispatch_after_app_calls_stream(client_factory) -> None:
    async def homepage(request):
        expected = [b"a", b""]
        async for chunk in request.stream():
            assert chunk == expected.pop(0)
        assert expected == []
        return PlainTextResponse("Homepage")

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            resp = await call_next(request)
            with pytest.raises(RuntimeError, match="Stream consumed"):
                async for _ in request.stream():
                    raise AssertionError("should not be called")  # pragma: no cover
            return resp

    app = Yaa(
        routes=[Route("/", homepage, methods=["POST"])],
        middlewares=[(ConsumingMiddleware, {})],
    )
    client = client_factory(app)
    response = client.post("/", content=b"a")
    assert response.status_code == 200


def test_read_request_stream_in_dispatch_after_app_calls_body(client_factory) -> None:
    async def homepage(request):
        assert await request.body() == b"a"
        return PlainTextResponse("Homepage")

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            resp = await call_next(request)
            with pytest.raises(RuntimeError, match="Stream consumed"):
                async for _ in request.stream():
                    raise AssertionError("should not be called")  # pragma: no cover
            return resp

    app = Yaa(
        routes=[Route("/", homepage, methods=["POST"])],
        middlewares=[(ConsumingMiddleware, {})],
    )
    client = client_factory(app)
    response = client.post("/", content=b"a")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_read_request_stream_in_dispatch_wrapping_app_calls_body() -> None:
    async def endpoint(scope, receive, send) -> None:
        request = Request(scope, receive)
        async for chunk in request.stream():
            assert chunk == b"2"
            break
        await Response()(scope, receive, send)

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            expected = b"1"
            response = None
            async for chunk in request.stream():
                assert chunk == expected
                if expected == b"1":
                    response = await call_next(request)
                    expected = b"3"
                else:
                    break
            assert response is not None
            return response

    async def rcv():
        yield {"type": "http.request", "body": b"1", "more_body": True}
        yield {"type": "http.request", "body": b"2", "more_body": True}
        yield {"type": "http.request", "body": b"3"}
        await anyio.sleep(float("inf"))

    sent = []

    async def send(msg) -> None:
        sent.append(msg)

    app = endpoint
    app = ConsumingMiddleware(app)
    rcv_stream = rcv()
    await app({"type": "http"}, rcv_stream.__anext__, send)
    assert sent == [
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-length", b"0")],
        },
        {"type": "http.response.body", "body": b"", "more_body": False},
    ]
    await rcv_stream.aclose()


def test_read_request_stream_in_dispatch_after_app_calls_body_with_middleware_calling_body_before_call_next(  # noqa: E501
    client_factory,
) -> None:
    async def homepage(request):
        assert await request.body() == b"a"
        return PlainTextResponse("Homepage")

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            assert (
                await request.body() == b"a"
            )  # this buffers the request body in memory
            resp = await call_next(request)
            async for chunk in request.stream():
                if chunk:
                    assert chunk == b"a"
            return resp

    app = Yaa(
        routes=[Route("/", homepage, methods=["POST"])],
        middlewares=[(ConsumingMiddleware, {})],
    )
    client = client_factory(app)
    response = client.post("/", content=b"a")
    assert response.status_code == 200


def test_read_request_body_in_dispatch_after_app_calls_body_with_middleware_calling_body_before_call_next(  # noqa: E501
    client_factory,
) -> None:
    async def homepage(request):
        assert await request.body() == b"a"
        return PlainTextResponse("Homepage")

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            assert (
                await request.body() == b"a"
            )  # this buffers the request body in memory
            resp = await call_next(request)
            assert await request.body() == b"a"  # no problem here
            return resp

    app = Yaa(
        routes=[Route("/", homepage, methods=["POST"])],
        middlewares=[(ConsumingMiddleware, {})],
    )
    client = client_factory(app)
    response = client.post("/", content=b"a")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_read_request_disconnected_client() -> None:
    """If we receive a disconnect message when the downstream ASGI
    app calls receive() the Request instance passed into the dispatch function
    should get marked as disconnected.
    The downstream ASGI app should not get a ClientDisconnect raised,
    instead if should just receive the disconnect message.
    """

    async def endpoint(scope, receive, send) -> None:
        msg = await receive()
        assert msg["type"] == "http.disconnect"
        await Response()(scope, receive, send)

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            disconnected = await request.is_disconnected()
            assert disconnected is True
            return response

    scope = {"type": "http", "method": "POST", "path": "/"}

    async def receive():
        yield {"type": "http.disconnect"}
        raise AssertionError("Should not be called, would hang")  # pragma: no cover

    async def send(msg):
        if msg["type"] == "http.response.start":
            assert msg["status"] == 200

    app = ConsumingMiddleware(endpoint)
    rcv = receive()
    await app(scope, rcv.__anext__, send)
    await rcv.aclose()


@pytest.mark.anyio
async def test_read_request_disconnected_after_consuming_steam() -> None:
    async def endpoint(scope, receive, send) -> None:
        msg = await receive()
        assert msg.pop("more_body", False) is False
        assert msg == {"type": "http.request", "body": b"hi"}
        msg = await receive()
        assert msg == {"type": "http.disconnect"}
        await Response()(scope, receive, send)

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            await request.body()
            disconnected = await request.is_disconnected()
            assert disconnected is True
            response = await call_next(request)
            return response

    scope = {"type": "http", "method": "POST", "path": "/"}

    async def receive():
        yield {"type": "http.request", "body": b"hi"}
        yield {"type": "http.disconnect"}
        raise AssertionError("Should not be called, would hang")  # pragma: no cover

    async def send(msg):
        if msg["type"] == "http.response.start":
            assert msg["status"] == 200

    app = ConsumingMiddleware(endpoint)
    rcv = receive()
    await app(scope, rcv.__anext__, send)
    await rcv.aclose()


def test_downstream_middleware_modifies_receive(client_factory) -> None:
    """If a downstream middleware modifies receive() the final ASGI app
    should see the modified version.
    """

    async def endpoint(scope, receive, send) -> None:
        request = Request(scope, receive)
        body = await request.body()
        assert body == b"foo foo "
        await Response()(scope, receive, send)

    class ConsumingMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            logger.debug("test -- 01", request)
            body = await request.body()
            assert body == b"foo "
            return await call_next(request)

    def modifying_middleware(app) -> ASGIApp:
        async def wrapped_app(scope, receive, send) -> None:
            async def wrapped_receive() -> Message:
                msg = await receive()
                if msg["type"] == "http.request":
                    msg["body"] = msg["body"] * 2
                return msg

            await app(scope, wrapped_receive, send)

        return wrapped_app

    client = client_factory(ConsumingMiddleware(modifying_middleware(endpoint)))
    resp = client.post("/", content=b"foo ")
    assert resp.status_code == 200


from yaa.responses import Response
from yaa.requests import Request
from yaa.types import ASGI3App as ASGIApp, Message

CallNext = typing.Callable[[Request], typing.Awaitable[Response]]


def test_pr_1519_comment_1236166180_example(client_factory) -> None:
    """
    https://github.com/encode/starlette/pull/1519#issuecomment-1236166180
    """
    bodies = []

    class LogRequestBodySize(BaseHttpMiddleware):
        async def dispatch(self, request, call_next) -> Response:
            return await call_next(request)

    def replace_body_middleware(app) -> ASGIApp:
        async def wrapped_app(scope, receive, send) -> None:
            async def wrapped_rcv() -> Message:
                msg = await receive()
                msg["body"] += b"-foo"
                return msg

            await app(scope, wrapped_rcv, send)

        return wrapped_app

    async def endpoint(request) -> Response:
        body = await request.body()
        bodies.append(body)
        return Response()

    app = Yaa(routes=[Route("/", endpoint, methods=["POST"])])
    app = replace_body_middleware(app)
    app = LogRequestBodySize(app)

    client = client_factory(app)
    resp = client.post("/", content=b"Hello, World!")
    resp.raise_for_status()
    assert bodies == [b"Hello, World!-foo"]


@pytest.mark.anyio
async def test_do_not_block_on_background_tasks():
    from typing import Callable, Awaitable

    request_body_sent = False
    response_complete = anyio.Event()
    events: List[Union[str, Message]] = []

    async def sleep_and_set():
        events.append("Background task started")
        await anyio.sleep(0.1)
        events.append("Background task finished")

    async def endpoint_with_background_task(_):
        logger.debug(f"{__name__}::endpoint_with_background_task")
        return PlainTextResponse(
            content="Hello", background=BackgroundTask(sleep_and_set)
        )

    async def passthrough(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        return await call_next(request)

    app = Yaa(
        middlewares=[(BaseHttpMiddleware, dict(dispatch=passthrough))],
        routes=[Route("/", endpoint_with_background_task)],
    )

    scope = {
        "type": "http",
        "version": "3",
        "method": "GET",
        "path": "/",
    }

    async def receive() -> Message:
        nonlocal request_body_sent
        if not request_body_sent:
            request_body_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await response_complete.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message):
        logger.debug(f"send message: {message!r}")
        if message["type"] == "http.response.body":
            events.append(message)
            if not message.get("more_body", False):
                response_complete.set()

    async with anyio.create_task_group() as tg:
        tg.start_soon(app, scope, receive, send)
        tg.start_soon(app, scope, receive, send)
    # Without the fix, the background tasks would start and finish before the
    # last http.response.body is sent.
    logger.debug(f"events: {events!r}")
    assert events == [
        {"body": b"Hello", "more_body": True, "type": "http.response.body"},
        {"body": b"", "more_body": False, "type": "http.response.body"},
        {"body": b"Hello", "more_body": True, "type": "http.response.body"},
        {"body": b"", "more_body": False, "type": "http.response.body"},
        "Background task started",
        "Background task started",
        "Background task finished",
        "Background task finished",
    ]
