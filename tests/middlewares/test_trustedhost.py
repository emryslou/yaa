import pytest

from yast.applications import Yast
from yast.middlewares import TrustedHostMiddleware
from yast.responses import PlainTextResponse
from yast.testclient import TestClient


def test_trustedhost():
    app = Yast()

    @app.route("/")
    async def home(_):
        return PlainTextResponse("OK")

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["aa.com", "bb.com"])

    client = TestClient(app, base_url="http://aa.com")
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "OK"

    client = TestClient(app, base_url="http://bb.com")
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "OK"

    client = TestClient(app, base_url="http://xx.com")
    res = client.get("/")
    assert res.status_code == 400
    assert res.text == "Invalid host header"


def test_wildcard():
    app = Yast()

    @app.route("/")
    async def home(_):
        return PlainTextResponse("OK")

    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["aa.com", "bb.com", "*.ff.com"]
    )

    client = TestClient(app, base_url="http://aa.com")
    res = client.get("/")
    assert res.status_code == 200

    client = TestClient(app, base_url="http://cc.aa.com")
    res = client.get("/")
    assert res.status_code == 400

    client = TestClient(app, base_url="http://kk.ff.com")
    res = client.get("/")
    assert res.status_code == 200

    client = TestClient(app, base_url="http://aa.ff.com")
    res = client.get("/")
    assert res.status_code == 200

    client = TestClient(app, base_url="http://ff.aa.com")
    res = client.get("/")
    assert res.status_code == 400
