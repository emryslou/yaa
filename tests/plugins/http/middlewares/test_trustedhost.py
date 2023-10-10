import pytest

from yaa.applications import Yaa
from yaa.responses import PlainTextResponse


@pytest.mark.timeout(30)
def test_trustedhost(client_factory):
    app = Yaa(
        plugins={
            "http": {
                "middlewares": {"trustedhost": dict(allowed_hosts=["aa.com", "bb.com"])}
            }
        }
    )

    @app.route("/")
    async def home(_):
        return PlainTextResponse("OK")

    client = client_factory(app, base_url="http://aa.com")
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "OK"

    client = client_factory(app, base_url="http://bb.com")
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "OK"

    client = client_factory(app, base_url="http://xx.com")
    res = client.get("/")
    assert res.status_code == 400
    assert res.text == "Invalid host header"


def test_wildcard(client_factory):
    app = Yaa(
        plugins={
            "http": {
                "middlewares": {
                    "trustedhost": dict(allowed_hosts=["aa.com", "bb.com", "*.ff.com"])
                }
            }
        }
    )

    @app.route("/")
    async def home(_):
        return PlainTextResponse("OK")

    client = client_factory(
        app,
        base_url="http://aa.com",
    )
    res = client.get("/")
    assert res.status_code == 200

    client = client_factory(app, base_url="http://cc.aa.com")
    res = client.get("/")
    assert res.status_code == 400

    client = client_factory(app, base_url="http://kk.ff.com")
    res = client.get("/")
    assert res.status_code == 200

    client = client_factory(app, base_url="http://aa.ff.com")
    res = client.get("/")
    assert res.status_code == 200

    client = client_factory(app, base_url="http://ff.aa.com")
    res = client.get("/")
    assert res.status_code == 400


def test_www_redirect(client_factory):
    app = Yaa(
        plugins={
            "http": {
                "middlewares": {"trustedhost": dict(allowed_hosts=["www.example.com"])}
            }
        }
    )

    @app.route("/")
    def homepage(request):
        return PlainTextResponse("OK", status_code=200)

    client = client_factory(app, base_url="https://example.com")
    response = client.get("/")
    assert response.status_code == 200
    assert response.url == "https://www.example.com/"


def test_default_allowed_hosts():
    app = Yaa(plugins={"http": {"middlewares": {"trustedhost": {}}}})

    from yaa.plugins.http.middlewares import TrustedHostMiddleware

    middleware = TrustedHostMiddleware(app)
    assert middleware.allowed_hosts == ["*"]
