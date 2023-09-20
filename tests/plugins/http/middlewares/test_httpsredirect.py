from yast.applications import Yast
from yast.responses import PlainTextResponse
from yast.testclient import TestClient


def test_httpsredirect():
    app = Yast(plugins={"http": {"middlewares": {"httpsredirect": {}}}})

    @app.route("/")
    async def home(_):
        return PlainTextResponse("OK")

    client = TestClient(app, base_url="https://testserver")
    res = client.get("/?type=https")
    assert res.status_code == 200

    client = TestClient(app)
    res = client.get("/?type=http", allow_redirects=False)
    assert res.status_code == 301
    assert res.headers["location"] == "https://testserver/?type=http"

    client = TestClient(app, base_url="http://testserver:80")
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "https://testserver/"
    client = TestClient(app, base_url="http://testserver:123")
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "https://testserver:123/"
