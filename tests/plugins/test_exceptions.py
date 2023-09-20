import pytest

from yast import TestClient
from yast.exceptions import HttpException
from yast.plugins.exceptions.middlewares.error import ExceptionMiddleware
from yast.responses import PlainTextResponse
from yast.routing import Route, Router


def raise_runtime_error(scope):
    async def asgi(receive, send):
        raise RuntimeError("W.c.")

    return asgi


def not_acceptable(scope):
    async def asgi(receive, send):
        raise HttpException(status_code=406)

    return asgi


def not_modified(scope):
    async def asgi(receive, send):
        raise HttpException(status_code=304)

    return asgi


def handled_exc_after_response(scope):
    async def asgi(receive, send):
        res = PlainTextResponse("OK", status_code=200)
        await res(receive, send)
        raise HttpException(status_code=406)

    return asgi


router = Router(
    [
        Route("/runtime_error", endpoint=raise_runtime_error),
        Route("/not_acceptable", endpoint=not_acceptable),
        Route("/not_modified", endpoint=not_modified),
        Route("/handled_exc_after_response", endpoint=handled_exc_after_response),
    ]
)

app = ExceptionMiddleware(router)
client = TestClient(app)


def test_debug_enabled():
    app = ExceptionMiddleware(router)
    app.debug = True

    client500 = TestClient(app, raise_server_exceptions=False)

    res = client500.get("/runtime_error")
    assert res.status_code == 500


def test_not_acceptable():
    res = client.get("/not_acceptable")
    assert res.status_code == 406
    assert "Not Acceptable" == res.text


def test_not_modified():
    res = client.get("/not_modified")
    assert res.status_code == 304
    assert "" == res.text


def test_websockets_should_raise():
    from yast.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.wsconnect("/runtime_error") as _:
            pass

    # with pytest.raises(RuntimeError):
    #     client.wsconnect('/runtime_error')


def test_handled_exc_after_response():
    with pytest.raises(RuntimeError):
        client.get("/handled_exc_after_response")

    client200 = TestClient(app, raise_server_exceptions=False)
    res = client200.get("handled_exc_after_response")
    assert res.status_code == 200
    assert res.text == "OK"


def test_force_500_res():
    def app(scope):
        raise RuntimeError()

    client_force_500 = TestClient(app, raise_server_exceptions=False)
    res = client_force_500.get("/")

    assert res.status_code == 500
    assert res.text == ""


def test_app_plugins():
    from yast import Yast

    app = Yast()
