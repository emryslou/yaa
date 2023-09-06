import os

from yast.applications import Yast
from yast.datastructures import Headers
from yast.lifespan import LifeSpanContext
from yast.requests import Request
from yast.responses import PlainTextResponse, JSONResponse
from yast.routing import Router
from yast.staticfiles import StaticFiles
from yast.testclient import TestClient

app = Yast()
client = TestClient(app)


@app.exception_handler(Exception)
async def error_500(req: Request, exc):
    return JSONResponse({"detail": "oo....ooo"}, status_code=500)


def _add_router():
    @app.route("/")
    def func_homepage(request):
        return PlainTextResponse("Hello, func_homepage")

    @app.route("/async")
    async def afun(request):
        return PlainTextResponse("Hello, afun")

    @app.route("/kwargs/{arg0}")
    def func_kwargs(request):
        return JSONResponse({"func": "func_kwargs", "path_params": request.path_params})

    @app.route("/kwargs1/{arg1}")
    def func_kwargs(request):
        return JSONResponse(
            {"func": "func_kwargs", "arg1": request.path_params["arg1"]}
        )


def test_func_route():
    _add_router()

    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Hello, func_homepage"

    res = client.get("/async")
    assert res.status_code == 200
    assert res.text == "Hello, afun"

    res = client.get("/kwargs/aaa")
    assert res.status_code == 200
    assert res.json() == {"func": "func_kwargs", "path_params": {"arg0": "aaa"}}

    res = client.get("/kwargs1/aaa")
    assert res.status_code == 200
    assert res.json() == {"func": "func_kwargs", "arg1": "aaa"}


def test_ws_route():
    @app.ws_route("/ws")
    async def ws_endpoint(session):
        await session.accept()
        await session.send_text("Hello, Ws")
        await session.close()

    with client.wsconnect("/ws") as s:
        text = s.receive_text()
        assert text == "Hello, Ws"


def test_400():
    _add_router()
    res = client.get("/404")
    assert res.status_code == 404


def test_app_mount(tmpdir):
    path = os.path.join(tmpdir, "example.txt")

    with open(path, "w") as f:
        f.write("<file content>")

    app.mount("/static", StaticFiles(directory=tmpdir))

    res = client.get("/static/example.txt")
    assert res.status_code == 200
    assert res.text == "<file content>"

    res = client.get("/static/nop.txt")
    assert res.status_code == 404


def test_app_error():
    client = TestClient(app, raise_server_exceptions=False)

    @app.route("/err_500")
    def _tmp(request: Request):
        raise Exception()

    res = client.get("/err_500")
    assert res.status_code == 500
    assert res.json() == {"detail": "oo....ooo"}

    res = client.post("/err_500")
    assert res.status_code == 405
    assert res.text == "Method Not Allowed"


def test_app_add_middleware():
    class TrustedHostMiddleware(object):
        def __init__(self, app, host) -> None:
            self.app = app
            self.host = host

        def __call__(self, scope):
            if scope["type"] in ("http", "websocket"):
                headers = Headers(scope=scope)
                if headers.get("host") != self.host:
                    return PlainTextResponse("Invalid host header", status_code=400)
            return self.app(scope)

    app.add_middleware(TrustedHostMiddleware, host="testserver")
    _add_router()
    client = TestClient(app, base_url="http://error")
    res = client.get("/")
    assert res.status_code == 400
    assert res.text == "Invalid host header"

    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Hello, func_homepage"


def test_app_add_event_handler():
    startup_complete = False
    cleanup_complete = False
    app = Yast()

    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    def run_cleanup():
        nonlocal cleanup_complete
        cleanup_complete = True

    app.add_event_handler("startup", run_startup)
    app.add_event_handler("shutdown", run_cleanup)
    assert not startup_complete
    assert not cleanup_complete
    with LifeSpanContext(app):
        assert startup_complete
        assert not cleanup_complete
    assert startup_complete
    assert cleanup_complete


def test_add_route():
    from yast import TestClient
    from yast.responses import PlainTextResponse

    app = Yast()

    async def homepage(_):
        return PlainTextResponse("homepage")

    app.add_route("/homepage", homepage)
    client = TestClient(app)

    res = client.get("/homepage")
    assert res.status_code == 200
    assert res.text == "homepage"


def test_add_ws():
    from yast import TestClient
    from yast.responses import PlainTextResponse

    app = Yast()

    async def ws_endpoint(ss):
        await ss.accept()
        await ss.send_text("Hello Ws")
        await ss.close()

    app.add_route_ws("/homepage", ws_endpoint)
    client = TestClient(app)

    with client.wsconnect("/homepage") as ss:
        text = ss.receive_text()
        assert text == "Hello Ws"
