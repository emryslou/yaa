import os
import pytest

from yast import TestClient
from yast.responses import Response, JSONResponse
from yast.routing import Route, Mount, NoMatchFound, Router, WebSocketRoute
from yast.staticfiles import StaticFiles
import yast.status as http_status
from yast.websockets import WebSocket, WebSocketDisconnect


def home(_):
    return Response("Hello Home", media_type="text/plain")


def users(req):
    content = req.path_params.get("username", None)
    if content is None:
        content = "All Users"
    else:
        content = "User %s" % content
    return Response(content, media_type="text/plain")


def staticfiles(req):
    return Response("xxxx", media_type="image/ping")


def http_endpoint(req):
    return Response("Hello, Http", media_type="text/plain")


app = Router(
    routes=[
        Route("/", endpoint=home, methods=["GET"]),
        Mount(
            "/users",
            app=Router(
                routes=[Route("", endpoint=users), Route("/{username}", endpoint=users)]
            ),
        ),
        Mount("/static", app=staticfiles),
    ]
)


@app.route("/func")
def func_home(req):
    return Response("func home", media_type="text/plain")


@app.route_ws("/ws")
async def ws_endpoint(ss):
    await ss.accept()
    await ss.send_text("Hello, Ws")
    await ss.close()


@app.route_ws("/ws/{room}")
async def ws_endpoint_room(ss):
    await ss.accept()
    await ss.send_text(f'Hello, Ws at {ss.path_params["room"]}')
    await ss.close()


client = TestClient(app)


def test_router():
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Hello Home"

    res = client.get("/func")
    assert res.status_code == 200
    assert res.text == "func home"

    res = client.post("/func")
    assert res.status_code == http_status.HTTP_405_METHOD_NOT_ALLOWED
    assert res.text == "Method Not Allowed"

    res = client.get("/users")
    assert res.status_code == 200
    assert res.text == "All Users"

    res = client.get("/users/Aa")
    assert res.status_code == 200
    assert res.text == "User Aa"

    res = client.get("/static")
    assert res.status_code == 200
    assert res.text == "xxxx"


def test_websocket():
    with client.wsconnect("/ws") as ss:
        text = ss.receive_text()
        assert text == "Hello, Ws"
    with client.wsconnect("/ws/abcd") as ss:
        text = ss.receive_text()
        assert text == "Hello, Ws at abcd"


def test_url_for():
    assert app.url_path_for("home") == "/"
    assert app.url_path_for("users", username="eml") == "/users/eml"
    assert app.url_path_for("users") == "/users"


def test_endpoint():
    from yast.endpoints import HttpEndPoint
    from yast.responses import HTMLResponse

    class DemoEndpoint(HttpEndPoint):
        def get(self, req):
            return HTMLResponse(self.__class__.__name__ + " OK")

    app.add_route("/demo", DemoEndpoint)

    res = client.get("/demo")
    assert res.status_code == 200
    assert res.text == "DemoEndpoint OK"
    res = client.post("/demo")
    assert res.status_code == http_status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.timeout(3)
def test_websocket_endpoint():
    from yast.endpoints import WebSocketEndpoint

    class WsApp(WebSocketEndpoint):
        encoding = "text"

        async def on_receive(self, data):
            await self.send(data + self.__class__.__name__, "text")

    app.add_route_ws("/ws_app", WsApp)
    with client.wsconnect("/ws_app") as ss:
        ss.send_text("hello")
        text = ss.receive_text()
        assert text == "helloWsApp"


@pytest.mark.timeout(3)
def test_mixed_app():
    from yast.routing import Route, WebSocketRoute

    mixed_app = Router(
        [Route("/", endpoint=http_endpoint), WebSocketRoute("/", endpoint=ws_endpoint)]
    )

    client = TestClient(mixed_app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Hello, Http"

    with client.wsconnect("/") as ss:
        text = ss.receive_text()
        assert text == "Hello, Ws"
