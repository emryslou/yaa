import pytest

from yast import TestClient
from yast.exceptions import HttpException
from yast.plugins.exceptions.middlewares.exception import ExceptionMiddleware
from yast.responses import PlainTextResponse
from yast.routing import Route, Router


async def raise_runtime_error(req):
    raise RuntimeError("W.c.")


async def not_acceptable(req):
    raise HttpException(status_code=406)


async def not_modified(req):
    raise HttpException(status_code=304)


router = Router(
    [
        Route("/runtime_error", endpoint=raise_runtime_error),
        Route("/not_acceptable", endpoint=not_acceptable),
        Route("/not_modified", endpoint=not_modified),
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
            pass  # pragma: no cover

    # with pytest.raises(RuntimeError):
    #     client.wsconnect('/runtime_error')


def test_force_500_res():
    def app(scope):
        raise RuntimeError()

    client_force_500 = TestClient(app, raise_server_exceptions=False)
    res = client_force_500.get("/")

    assert res.status_code == 500
    assert res.text == ""


def test_plugins_servererror():
    from yast import Yast

    def handle_exc(req, exc):
        return PlainTextResponse("srv err")

    app = Yast(
        plugins={
            "exceptions": {
                "middlewares": {
                    "servererror": {
                        "handler": handle_exc,
                    },
                    "exception": {},
                }
            }
        }
    )

    @app.route("/r_exc")
    def r_rexc(req):
        raise Exception()

    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/r_exc")
    assert res.status_code == 200
    assert res.text == "srv err"


def test_plugins_exception():
    from yast import Yast
    from yast.exceptions import HttpException

    class MyException(Exception):
        pass

    def handle_my(req, exc):
        return PlainTextResponse("my_exc")

    def handle_429(req, exc):
        return PlainTextResponse("sc:429")

    def handle_419(req, exc):
        return PlainTextResponse("sc:419")

    app = Yast(
        plugins={
            "exceptions": {
                "middlewares": {
                    "servererror": {},
                    "exception": {
                        "handlers": {
                            MyException: handle_my,
                            429: handle_429,
                            419: handle_419,
                        },
                    },
                }
            }
        }
    )

    @app.route("/r_my")
    def r_my(req):
        raise MyException()

    @app.route("/r_429")
    def r_my(req):
        raise HttpException(429)

    @app.route("/r_419")
    def r_my(req):
        raise HttpException(419)

    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/r_my")
    assert res.status_code == 200
    assert res.text == "my_exc"

    res = client.get("/r_429")
    assert res.status_code == 200
    assert res.text == "sc:429"

    res = client.get("/r_419")
    assert res.status_code == 200
    assert res.text == "sc:419"
