import pytest

from yaa.applications import Yaa
from yaa.middlewares import Middleware, BaseHttpMiddleware
from yaa.responses import PlainTextResponse
from yaa.routing import Route


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
