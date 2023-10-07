import os

from yast.applications import Yast
from yast.datastructures import Headers
from yast.requests import Request
from yast.responses import JSONResponse, PlainTextResponse
from yast.routing import Router
from yast.staticfiles import StaticFiles
from yast.testclient import TestClient


app = Yast()
client = TestClient(app)


@app.exception_handler(Exception)
async def error_500(req: Request, exc):
    return JSONResponse({"detail": "oo....ooo"}, status_code=500)


def _add_router(app):
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
    _add_router(app)

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
    _add_router(app)
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
    app = Yast(
        plugins={
            "http": {"middlewares": {"trustedhost": dict(allowed_hosts=["testserver"])}}
        }
    )
    _add_router(app)
    client = TestClient(app, base_url="http://error")
    res = client.get("/")
    assert res.status_code == 400
    assert res.text == "Invalid host header"

    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Hello, func_homepage"


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

    res = client.head("/homepage", stream=True)
    assert res.status_code == 200
    # assert res.text == ""


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


def test_exception_handler():
    from yast import TestClient
    from yast.responses import PlainTextResponse

    app = Yast()

    @app.exception_handler(500)
    async def err_500(req, _):
        return PlainTextResponse("Err 500", status_code=500)

    @app.exception_handler(405)
    async def err_405(req, _):
        return PlainTextResponse("Err 405", status_code=405)

    @app.route("/500")
    def _(_):
        raise RuntimeError("RtErr")

    @app.route("/405", methods=["GET"])
    def _405(_):
        return PlainTextResponse("405")

    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/500")
    assert res.status_code == 500
    assert res.text == "Err 500"

    res = client.get("/405")
    assert res.status_code == 200
    assert res.text == "405"

    res = client.post("/405")
    assert res.status_code == 405
    assert res.text == "Err 405"


def test_subdomain():
    app = Yast(
        plugins={
            "http": {
                "middlewares": {
                    "trustedhost": dict(allowed_hosts=["testserver", "*.example.org"])
                }
            }
        }
    )
    subdomain = Router()

    @subdomain.route("/")
    def r_subdomain(req):
        return PlainTextResponse("Subdomain:" + req.path_params["subdomain"])

    app.host("{subdomain}.example.org", subdomain)

    _add_router(app)

    client = TestClient(app, base_url="http://what.example.org")
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Subdomain:what"

    client = TestClient(app, base_url="http://abc.example.org")
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Subdomain:abc"


def test_add_exception():
    app = Yast()

    @app.exception_handler(Exception)
    async def exception(req, exc: Exception):
        print("exc")
        if exc.__cause__ is not None:
            print("exc ", exc.__cause__)
        return JSONResponse(content={"error": "Srv Err 2333"})

    @app.route("/")
    async def _(_):
        raise Exception("///")

    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/")
    assert res.json() == {"error": "Srv Err 2333"}
