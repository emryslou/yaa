import os, pytest

import yast.status as http_status

from yast import TestClient
from yast.responses import JSONResponse, PlainTextResponse, Response
from yast.routing import Host, Mount, NoMatchFound, Route, Router, WebSocketRoute
from yast.staticfiles import StaticFiles
from yast.websockets import WebSocket, WebSocketDisconnect


def home(_):
    return Response("Hello Home", media_type="text/plain")


def users(req):
    content = req.path_params.get("username", None)
    if content is None:
        content = "All Users"
    else:
        content = f"User {content}"
    return Response(content, media_type="text/plain")


def http_endpoint(req):
    return Response("Hello, Http", media_type="text/plain")


app = Router(
    routes=[
        Route("/", endpoint=home, methods=["GET"]),
        Mount(
            "/users",
            app=Router(
                routes=[
                    Route("/", endpoint=users),
                    Route("/{username}", endpoint=users),
                ]
            ),
        ),
        Mount("/static", app=Response("xxxx", media_type="image/png")),
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


def test_url_for():
    assert (
        app.url_path_for("home").make_absolute_url(base_url="https://example.org")
        == "https://example.org/"
    )

    assert (
        app.url_path_for("users", username="eml").make_absolute_url(
            base_url="https://example.org"
        )
        == "https://example.org/users/eml"
    )
    assert (
        app.url_path_for("ws_endpoint").make_absolute_url(
            base_url="https://example.org"
        )
        == "wss://example.org/ws"
    )


def test_mount_urls():
    mounted = Router([Mount("/users", PlainTextResponse("OK"), name="users")])
    client = TestClient(mounted)
    assert client.get("/users").status_code == 200
    assert client.get("/users").url == "http://testserver/users/"
    assert client.get("/users/").status_code == 200
    assert client.get("/users/a").status_code == 200
    assert client.get("/usersa").status_code == 404


def test_reverse_mount_urls():
    mounted = Router([Mount("/users", PlainTextResponse("OK"), name="users")])
    assert mounted.url_path_for("users", path="/a") == "/users/a"
    users = Router([Route("/{username}", PlainTextResponse("OK"), name="user")])
    mounted = Router([Mount("/{subpath}/users", users, name="users")])
    assert (
        mounted.url_path_for("users:user", subpath="test", username="tom")
        == "/test/users/tom"
    )
    assert (
        mounted.url_path_for("users", subpath="test", path="/tom") == "/test/users/tom"
    )


def test_path_params_convert():
    @app.route("/int/{param:int}", name="int_conv")
    def int_conv(req):
        num = req.path_params["param"]
        return JSONResponse({"int": num})

    @app.route("/float/{param:float}", name="float_conv")
    def float_conv(req):
        num = req.path_params["param"]
        return JSONResponse({"float": num})

    @app.route("/path/{param:path}", name="path_conv")
    def path_conv(req):
        num = req.path_params["param"]
        return JSONResponse({"path": num})

    res = client.get("/int/12")
    assert res.status_code == 200
    assert res.json() == {"int": 12}
    assert app.url_path_for("int_conv", param=12) == "/int/12"
    with pytest.raises(AssertionError) as exc:
        assert app.url_path_for("int_conv", param=-12)
    assert "Negative integers" in str(exc)

    res = client.get("/float/12.12")
    assert res.status_code == 200
    assert res.json() == {"float": 12.12}
    assert app.url_path_for("float_conv", param=12.0) == "/float/12"
    with pytest.raises(AssertionError) as exc:
        app.url_path_for("float_conv", param=-12.4)
    assert "Negative floats" in str(exc)
    with pytest.raises(AssertionError) as exc:
        app.url_path_for("float_conv", param="nan")
    assert "Negative floats" in str(exc)

    res = client.get("/float/12.345")
    assert res.status_code == 200
    assert res.json() == {"float": 12.345}

    res = client.get("/path/demo/abc")
    assert res.status_code == 200
    assert res.json() == {"path": "demo/abc"}
    assert app.url_path_for("path_conv", param="demo/abc") == "/path/demo/abc"


def users_api(request):
    return JSONResponse({"users": [{"username": "eml"}]})


mixed_hosts_app = Router(
    routes=[
        Host(
            "www.example.org",
            app=Router(
                [
                    Route("/", home, name="home"),
                    Route("/users", users, name="users"),
                ]
            ),
        ),
        Host(
            "api.example.org",
            name="api",
            app=Router([Route("/users", users_api, name="users")]),
        ),
    ]
)


def test_host_routing():
    client = TestClient(mixed_hosts_app, base_url="https://api.example.org/")
    response = client.get("/users")
    assert response.status_code == 200
    assert response.json() == {"users": [{"username": "eml"}]}
    response = client.get("/")
    assert response.status_code == 404
    client = TestClient(mixed_hosts_app, base_url="https://www.example.org/")
    response = client.get("/users")
    assert response.status_code == 200
    assert response.text == "All Users"
    response = client.get("/")
    assert response.status_code == 200


def test_host_reverse_urls():
    assert (
        mixed_hosts_app.url_path_for("home").make_absolute_url("https://whatever")
        == "https://www.example.org/"
    )
    assert (
        mixed_hosts_app.url_path_for("users").make_absolute_url("https://whatever")
        == "https://www.example.org/users"
    )
    assert (
        mixed_hosts_app.url_path_for("api:users").make_absolute_url("https://whatever")
        == "https://api.example.org/users"
    )


async def subdomain_app_(scope, receive, send):
    await JSONResponse({"subdomain": scope["path_params"]["subdomain"]})(
        scope, receive, send
    )


subdomain_app = Router(
    routes=[Host("{subdomain}.example.org", app=subdomain_app_, name="subdomains")]
)


def test_subdomain_routing():
    client = TestClient(subdomain_app, base_url="https://foo.example.org/")
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"subdomain": "foo"}


def test_subdomain_reverse_urls():
    assert (
        subdomain_app.url_path_for(
            "subdomains", subdomain="foo", path="/homepage"
        ).make_absolute_url("https://whatever")
        == "https://foo.example.org/homepage"
    )


def test_mount_routes():
    def aa(req):
        return PlainTextResponse("aa")

    app = Router([Mount("/mount", routes=[Route("/aa", endpoint=aa)])])

    client = TestClient(app)
    res = client.get("/mount/aa")
    assert res.status_code == 200
    assert res.text == "aa"

    app = Router([Mount("/mount", app=Router([Route("/aa", endpoint=aa)]))])
    client = TestClient(app)
    res = client.get("/mount/aa")
    assert res.status_code == 200
    assert res.text == "aa"

    with pytest.raises(AssertionError):
        app = Router([Mount("/mount")])


def test_mount_at_root():
    mounted = Router([Mount("/", PlainTextResponse("OK"), name="users")])
    client = TestClient(mounted)
    assert client.get("/").status_code == 200
