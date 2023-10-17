import anyio, pytest
from contextlib import AsyncExitStack

from yaa.applications import Yaa
from yaa.background import BackgroundTask
from yaa.middlewares import Middleware, BaseHttpMiddleware
from yaa.responses import PlainTextResponse, StreamingResponse
from yaa.routing import Route
from yaa.types import Scope, Receive, Send


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
        # small delay to give BaseHTTPMiddleware a chance to cancel us
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
        # small delay to give BaseHTTPMiddleware a chance to cancel us
        # this is required to make the test fail prior to fixing the issue
        # so do not be surprised if you remove it and the test still passes
        await anyio.sleep(0.1)
        context_manager_exited.set()

    class ContextManagerMiddleware:
        def __init__(self, app, **kwargs):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
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
