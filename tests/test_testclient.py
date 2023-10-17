import anyio
import pytest

from yaa.applications import Yaa
from yaa.responses import JSONResponse
from yaa.websockets import WebSocket, WebSocketDisconnect

mock_service = Yaa()


@mock_service.route("/")
def mock_service_endpoint(request):
    return JSONResponse({"mock": "example"})


app = Yaa()


@app.route("/")
def homepage(request):
    from yaa.testclient import TestClient

    client = TestClient(mock_service)
    response = client.get("/")
    return JSONResponse(response.json())


startup_error_app = Yaa()


@startup_error_app.on_event("startup")
def startup():
    raise RuntimeError()


def test_use_testclient_in_endpoint(client_factory):
    """
    We should be able to use the test client within applications.

    This is useful if we need to mock out other services,
    during tests or in development.
    """
    client = client_factory(app)
    response = client.get("/")
    assert response.json() == {"mock": "example"}


@pytest.mark.timeout(3)
def testclient_as_contextmanager(client_factory):
    with client_factory(app):
        pass


def test_error_on_startup(client_factory):
    with pytest.raises(RuntimeError):
        with client_factory(startup_error_app):
            pass  # pragma: no cover


def test_testclient_asgi2(client_factory):
    def app(scope):
        async def inner(receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [[b"content-type", b"text/plain"]],
                }
            )
            await send({"type": "http.response.body", "body": b"Hello, world!"})

        return inner

    client = client_factory(app)
    response = client.get("/")
    assert response.text == "Hello, world!"


def test_testclient_asgi3(client_factory):
    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            }
        )
        await send({"type": "http.response.body", "body": b"Hello, world!"})

    client = client_factory(app)
    response = client.get("/")
    assert response.text == "Hello, world!"


def test_websocket_blocking_receive(client_factory):
    def app(scope):
        async def respond(websocket):
            await websocket.send_json({"message": "test"})

        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            async with anyio.create_task_group() as tg:
                tg.start_soon(respond, websocket)
                # asyncio.ensure_future(respond(websocket))
                try:
                    # this will block as the client does not send us data
                    # it should not prevent `respond` from executing though
                    await websocket.receive_json()
                except WebSocketDisconnect:
                    pass

        return asgi

    client = client_factory(app)
    with client.wsconnect("/") as websocket:
        data = websocket.receive_json()
        assert data == {"message": "test"}


def test_client(client_factory):
    async def app(scope, receive, send):
        client = scope.get("client")
        assert client is not None
        host, port = client
        response = JSONResponse({"host": host, "port": port})
        await response(scope, receive, send)

    client = client_factory(app)
    response = client.get("/")
    assert response.json() == {"host": "testclient", "port": 50000}


@pytest.mark.parametrize("param", ("2020-07-14T00:00:00+00:00", "España", "voilà"))
def test_query_params(client_factory, param: str):
    from yaa.routing import Route
    from yaa.responses import Response

    def homepage(request):
        return Response(request.query_params["param"])

    app = Yaa(routes=[Route("/", endpoint=homepage)])
    client = client_factory(app)
    response = client.get("/", params={"param": param})
    assert response.text == param


def test_testclient_headers_behavior():
    from yaa.testclient import TestClient

    client = TestClient(mock_service)
    assert client.headers.get("user-agent") == "testclient"

    client = TestClient(mock_service, headers={"user-agent": "non-default-agent"})
    assert client.headers.get("user-agent") == "non-default-agent"

    client = TestClient(mock_service, headers={"Authentication": "Bearer 123"})
    assert client.headers.get("user-agent") == "testclient"
    assert client.headers.get("Authentication") == "Bearer 123"
