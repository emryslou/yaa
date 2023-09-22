import pytest

from yast import TestClient
from yast.plugins.exceptions.middlewares.server import (
    ServerErrorMiddleware,
    req_method_content_length_eq_0,
)
from yast.responses import JSONResponse


def test_handler():
    async def app(scope, receive, send):
        raise RuntimeError("Some error happens")


    def error_500(req, exc):
        return JSONResponse({"detail": "Srv Err"}, status_code=500)

    app = ServerErrorMiddleware(app, handler=error_500)
    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/")
    assert res.status_code == 500
    assert res.json() == {"detail": "Srv Err"}


def test_debug_text():
    async def app(scope, receive, send):
        raise RuntimeError("Some error happens")


    app = ServerErrorMiddleware(app, debug=True)
    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/", headers={"Accept": "text/plain, */*"})
    assert res.status_code == 500
    assert res.headers["content-type"].startswith("text/plain")
    assert "RuntimeError" in res.text


def test_debug_html():
    async def app(scope, receive, send):
        raise RuntimeError("Some error happens")


    app = ServerErrorMiddleware(app, debug=True)
    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/", headers={"Accept": "text/html, */*"})
    assert res.status_code == 500
    assert res.headers["content-type"].startswith("text/html")
    assert "<h2>" in res.text
    assert "RuntimeError" in res.text


def test_error_during_scope():
    async def app(scope, receive, send):
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

    async def app(scope, receive, send):
        raise RuntimeError("Something went wrong")

    app = ServerErrorMiddleware(app)
    with pytest.raises(RuntimeError):
        app({"type": "websocket"}, None, None)


def test_req_method_head_content_length_eq_0():
    cases_headers = [
        [
            (b"content-length", b"8"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
        ],
        [
            (b"aaaaa", b"cccccc"),
            (b"content-length", b"8"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
        ],
        [
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"content-length", b"8"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
        ],
        [
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"content-length", b"8"),
            (b"aaaaa", b"cccccc"),
        ],
        [
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"content-length", b"8"),
        ],
        [
            (b"content-length", b"8"),
        ],
        [
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
            (b"aaaaa", b"cccccc"),
        ],
    ]

    for idx, headers in enumerate(cases_headers):
        newheader = req_method_content_length_eq_0(headers)
        assert len(headers) == len(newheader), "%d failure" % (idx + 1)
