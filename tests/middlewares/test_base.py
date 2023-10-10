import typing

import pytest

from yaa import Yaa
from yaa.middlewares import BaseHttpMiddleware
from yaa.requests import Request
from yaa.responses import PlainTextResponse
from yaa.types import ASGIInstance


class VenderMiddleware(BaseHttpMiddleware):
    async def dispatch(self, req: Request, call_next: typing.Callable) -> ASGIInstance:
        res = await call_next(req)
        res.headers["Vendor-Header"] = "Vendor"
        return res


app = Yaa()
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

    def __await__(self) -> typing.Generator:
        return self.__call__().__await__()

    async def __call__(self):
        pass


@pytest.mark.timeout(3)
def test_vendor(client_factory):
    client = client_factory(app)
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
def test_decorator(client_factory):
    app = Yaa()

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

    client = client_factory(app)
    res = client.get("/")
    assert res.text == "OK"

    res = client.get("/homepage")
    assert res.text == "Homepage"
    assert res.headers["Handler"] == "@Func"


def test_state_data_across_multiple_middlewares(client_factory):
    expected_value = "yes"

    class aMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.show_me = expected_value
            response = await call_next(request)
            return response

    class bMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            response.headers["X-State-Show-Me"] = request.state.show_me
            return response

    app = Yaa()
    app.add_middleware(aMiddleware)
    app.add_middleware(bMiddleware)

    @app.route("/")
    def homepage(request):
        return PlainTextResponse("OK")

    client = client_factory(app)
    response = client.get("/")
    assert response.text == "OK"
    assert response.headers["X-State-Show-Me"] == expected_value


def test_multiple_middlewares_run_order(client_factory):
    class aMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request: Request, call_next):
            if not hasattr(request.state, "show_me"):
                request.state.show_me = self.__class__.__name__
            else:
                request.state.show_me += "," + self.__class__.__name__
            response = await call_next(request)
            response.headers["X-State-Show-Me"] = request.state.show_me
            return response

    class bMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            if not hasattr(request.state, "show_me"):
                request.state.show_me = self.__class__.__name__
            else:
                request.state.show_me += "," + self.__class__.__name__
            response = await call_next(request)

            return response

    class cMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            if not hasattr(request.state, "show_me"):
                request.state.show_me = self.__class__.__name__
            else:
                request.state.show_me += "," + self.__class__.__name__
            response = await call_next(request)

            return response

    class dMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            if not hasattr(request.state, "show_me"):
                request.state.show_me = self.__class__.__name__
            else:
                request.state.show_me += "," + self.__class__.__name__
            response = await call_next(request)

            return response

    app = Yaa(
        middlewares=[(aMiddleware, {}), (bMiddleware, {})], plugins={"session": {}}
    )
    app.add_middleware(cMiddleware)
    app.add_middleware(dMiddleware)

    @app.route("/")
    def homepage(request: Request):
        return PlainTextResponse("OK")

    client = client_factory(app)
    response = client.get("/")
    assert response.text == "OK"
    assert (
        response.headers["X-State-Show-Me"]
        == "aMiddleware,bMiddleware,cMiddleware,dMiddleware"
    )
