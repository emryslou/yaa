from yaa import TestClient, Yaa
from yaa.responses import HTMLResponse


async def app(scope, recv, send):
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"Hello"})


def test_app(client_factory):
    client = client_factory(app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Hello"
