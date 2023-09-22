import typing

import pytest

from yast import TestClient, Yast
from yast.middlewares import BaseHttpMiddleware
from yast.requests import Request
from yast.responses import PlainTextResponse
from yast.types import ASGIInstance


class VenderMiddleware(BaseHttpMiddleware):
    async def dispath(self, req: Request, call_next: typing.Callable) -> ASGIInstance:
        res = await call_next(req)
        res.headers["Vendor-Header"] = "Vendor"
        return res


app = Yast()
app.add_middleware(VenderMiddleware)


@app.route("/")
def _(_):
    return PlainTextResponse("index")


@app.route("/exc")
def exc(_):
    raise Exception()


@app.route("/rterr")
def rterr(_):
    raise RuntimeError()


@app.ws_route("/ws")
async def ws_ep(s):
    await s.accept()
    await s.send_text("ws_ep")
    await s.close()


@app.route("/no_res")
class NoResApp:
    def __init__(self, *args, **kwargs):
        pass

    async def __call__(self, scope, receive, send):
        pass


@pytest.mark.timeout(3)
def test_vendor():
    client = TestClient(app)
    res = client.get("/")
    assert "Vendor-Header" in res.headers
    assert res.headers["Vendor-Header"] == "Vendor"

    with pytest.raises(Exception):
        response = client.get("/exc")
    with pytest.raises(RuntimeError):
        response = client.get("/rterr")

    with client.wsconnect("/ws") as session:
        text = session.receive_text()
        assert text == "ws_ep"

    with pytest.raises(RuntimeError):
        client.get("/no_res")


@pytest.mark.timeout(3)
def test_decorator():
    app = Yast()

    @app.route("/homepage")
    def _(_):
        return PlainTextResponse("Homepage")

    @app.middleware("http")
    async def plaintext(req, call_next):
        if req.url.path == "/":
            return PlainTextResponse("OK")
        res = await call_next(req)
        res.headers["Handler"] = "@Func"
        return res

    client = TestClient(app)
    res = client.get("/")
    assert res.text == "OK"

    res = client.get("/homepage")
    assert res.text == "Homepage"
    assert res.headers["Handler"] == "@Func"
