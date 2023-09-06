from yast import TestClient, Yast
from yast.responses import HTMLResponse


def app(scope):
    async def asgi(recv, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"Hello"})

    return asgi


def test_app():
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Hello"
