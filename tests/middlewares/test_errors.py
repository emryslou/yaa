import pytest

from yast import TestClient
from yast.plugins.exceptions.middlewares.server import ServerErrorMiddleware
from yast.responses import JSONResponse


def test_handler():
    def app(scope):
        async def asgi(rec, send):
            raise RuntimeError("Some error happens")

        return asgi

    def error_500(req, exc):
        return JSONResponse({"detail": "Srv Err"}, status_code=500)

    app = ServerErrorMiddleware(app, handler=error_500)
    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/")
    assert res.status_code == 500
    assert res.json() == {"detail": "Srv Err"}


def test_debug_text():
    def app(scope):
        async def asgi(rec, send):
            raise RuntimeError("Some error happens")

        return asgi

    app = ServerErrorMiddleware(app, debug=True)
    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/", headers={"Accept": "text/plain, */*"})
    assert res.status_code == 500
    assert res.headers["content-type"].startswith("text/plain")
    assert "RuntimeError" in res.text


def test_debug_html():
    def app(scope):
        async def asgi(rec, send):
            raise RuntimeError("Some error happens")

        return asgi

    app = ServerErrorMiddleware(app, debug=True)
    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/", headers={"Accept": "text/html, */*"})
    assert res.status_code == 500
    assert res.headers["content-type"].startswith("text/html")
    assert "<h2>" in res.text
    assert "RuntimeError" in res.text


def test_error_during_scope():
    def app(scope):
        raise RuntimeError("Some error happens")

    app = ServerErrorMiddleware(app, debug=True)
    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/", headers={"Accept": "text/html, */*"})
    assert res.status_code == 500
    assert res.headers["content-type"].startswith("text/html")
    assert "RuntimeError" in res.text


def test_debug_not_http():
    """
    DebugMiddleware should just pass through any non-http messages as-is.
    """

    def app(scope):
        raise RuntimeError("Something went wrong")

    app = ServerErrorMiddleware(app)
    with pytest.raises(RuntimeError):
        app({"type": "websocket"})
