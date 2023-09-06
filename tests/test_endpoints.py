import typing

import pytest

from yast.endpoints import HttpEndPoint, WebSocketEndpoint
from yast.requests import Request
from yast.responses import PlainTextResponse
from yast.routing import Route, Router
from yast.testclient import TestClient
from yast.websockets import WebSocket


class HomePage(HttpEndPoint):
    async def get(self, req: Request):
        username = req.path_params.get("username", None)
        if username is None:
            return PlainTextResponse("Hello, all of you")
        else:
            return PlainTextResponse(f"Hello, {username}")


app = Router(
    routes=[
        Route("/", endpoint=HomePage),
        Route("/{username}", endpoint=HomePage),
    ]
)
client = TestClient(app)


def test_http_endpoint_route():
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Hello, all of you"

    res = client.get("/abc")
    assert res.status_code == 200
    assert res.text == "Hello, abc"

    # res = client.post('/abc')
    # assert res.status_code == 405
    # assert res.text == 'Method Not Allowed'


def test_websocket_endpoint_on_connect():
    class WsApp(WebSocketEndpoint):
        async def on_connect(self, **kwargs: typing.Any) -> None:
            assert self.ws["subprotocols"] == ["soap", "wamp"]
            await self.ws.accept(subprotocol="wamp")

    client = TestClient(WsApp)
    with client.wsconnect("/ws", subprotocols=["soap", "wamp"]) as s:
        s.accepted_subprotocol == "wamp"


@pytest.mark.timeout(3)
def test_websocket_endpoint_on_receive_bytes():
    class WsApp(WebSocketEndpoint):
        encoding = "bytes"

        async def on_receive(self, data) -> None:
            await self.send(b"Received msg is " + data)

        async def on_disconnect(self, code: int) -> None:
            pass

    client = TestClient(WsApp)
    with client.wsconnect("/ws") as s:
        msg = "Hello, Bytes"
        s.send_bytes(msg.encode("utf-8"))
        s.receive_bytes() == (f"Received msg is {msg}").encode("utf-8")
