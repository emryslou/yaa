import pytest

from yast import TestClient
from yast.debug import DebugMiddleware
from yast.responses import Response


def test_debug_text():
    def app(scope):
        async def asgi(receive, send):
            raise RuntimeError("Text:Something went wrong")

        return asgi

    client = TestClient(DebugMiddleware(app), raise_server_exceptions=False)
    res = client.get("/")
    assert res.status_code == 500
    assert "<html>" not in res.text
    assert "Text:Something went wrong" in res.text


def test_debug_html():
    def app(scope):
        async def asgi(receive, send):
            raise RuntimeError("Something went wrong")

        return asgi

    client = TestClient(DebugMiddleware(app), raise_server_exceptions=False)
    res = client.get("/", headers={"accept": "text/html, */*"})
    assert res.status_code == 500
    assert res.headers["content-type"].startswith("text/html")
    assert "<html>" in res.text
    assert "Something went wrong" in res.text


def test_debug_after_response_sent():
    def app(scope):
        async def asgi(receive, send):
            res = Response(b"", status_code=204)
            await res(receive, send)
            raise RuntimeError("Something went wrong")

        return asgi

    client = TestClient(DebugMiddleware(app))
    with pytest.raises(RuntimeError):
        res = client.get("/", headers={"accept": "text/html, */*"})


def test_debug_error_during_scope():
    def app(scope):
        async def asgi(receive, send):
            raise RuntimeError("Something went wrong")

        return asgi

    client = TestClient(
        DebugMiddleware(DebugMiddleware(app)), raise_server_exceptions=False
    )

    res = client.get("/", headers={"accept": "text/html, */*"})
    assert res.status_code == 500
    assert res.headers["content-type"].startswith("text/html")
    assert "Something went wrong" in res.text


def test_debug_not_http():
    def app(scope):
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)

    with pytest.raises(RuntimeError):
        app({"type": "websocket"})
