import os, pytest

import yast.status as http_status

from yast import TestClient, Yast
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


# Route with chars that conflict with regex meta chars
@app.route("/path-with-parentheses({param:int})", name="path-with-parentheses")
def path_with_parentheses(request):
    number = request.path_params["param"]
    return JSONResponse({"int": number})


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

    # Test path with parentheses
    res = client.get("/path-with-parentheses(7)")
    assert res.status_code == 200
    assert res.json() == {"int": 7}
    assert (
        app.url_path_for("path-with-parentheses", param=10)
        == "/path-with-parentheses(10)"
    )


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
    assert (
        app.url_path_for("home").make_absolute_url(base_url="https://ex.org/root_path/")
        == "https://ex.org/root_path/"
    )
    assert (
        app.url_path_for("user", username="eml").make_absolute_url(
            base_url="https://example.org/root_path/"
        )
        == "https://example.org/root_path/users/eml"
    )


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

    @app.route("/uuid/{param:uuid}", name="uuid_conv")
    def uuid_conv(req):
        param = req.path_params["param"]
        return JSONResponse({"uuid": str(param)})

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

    res = client.get("/uuid/01234567-89ab-cdef-0123-456789abcdef")
    assert res.status_code == 200
    assert res.json() == {"uuid": "01234567-89ab-cdef-0123-456789abcdef"}
    assert (
        app.url_path_for("uuid_conv", param="fecdba98-7654-3210-fecd-ba9876543210")
        == "/uuid/fecdba98-7654-3210-fecd-ba9876543210"
    )


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


async def echo_urls(request):
    return JSONResponse(
        {
            "index": request.url_for("index"),
            "submount": request.url_for("mount:submount"),
        }
    )


echo_url_routes = [
    Route("/", echo_urls, name="index", methods=["GET"]),
    Mount(
        "/submount",
        name="mount",
        routes=[Route("/", echo_urls, name="submount", methods=["GET"])],
    ),
]


def test_url_for_with_root_path():
    app = Yast(routes=echo_url_routes)
    client = TestClient(app, base_url="https://www.example.org/", root_path="/sub_path")
    response = client.get("/")
    assert response.json() == {
        "index": "https://www.example.org/sub_path/",
        "submount": "https://www.example.org/sub_path/submount/",
    }
    response = client.get("/submount/")
    assert response.json() == {
        "index": "https://www.example.org/sub_path/",
        "submount": "https://www.example.org/sub_path/submount/",
    }


double_mount_routes = [
    Mount(
        "/mount",
        name="mount",
        routes=[Mount("/static", ..., name="static")],
    ),
]


def test_url_for_with_double_mount():
    app = Yast(routes=double_mount_routes)
    url = app.url_path_for("mount:static", path="123")
    assert url == "/mount/static/123"


def test_partial_async_endpoint():
    import functools

    async def _partial_async_endpoint(arg, request):
        return JSONResponse({"arg": arg})

    partial_async_endpoint = functools.partial(_partial_async_endpoint, "foo")
    partial_async_app = Router(routes=[Route("/", partial_async_endpoint)])

    response = TestClient(partial_async_app).get("/")
    assert response.status_code == 200
    assert response.json() == {"arg": "foo"}


def test_duplicated_param_names():
    with pytest.raises(
        ValueError,
        match="Duplicated param name id at path /{id}/{id}",
    ):
        Route("/{id}/{id}", users)
    with pytest.raises(
        ValueError,
        match="Duplicated param names id, name at path /{id}/{name}/{id}/{name}",
    ):
        Route("/{id}/{name}/{id}/{name}", users)
