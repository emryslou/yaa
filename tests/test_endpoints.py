import typing
import inspect
import pytest

from yaa.endpoints import HttpEndPoint, WebSocketEndpoint
from yaa.requests import Request
from yaa.responses import PlainTextResponse
from yaa.routing import Route, Router
from yaa.websockets import WebSocket


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


def test_http_endpoint_route(client_factory):
    client = client_factory(app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "Hello, all of you"

    res = client.get("/abc")
    assert res.status_code == 200
    assert res.text == "Hello, abc"

    # res = client.post('/abc')
    # assert res.status_code == 405
    # assert res.text == 'Method Not Allowed'


def test_websocket_endpoint_on_connect(client_factory):
    class WsApp(WebSocketEndpoint):
        async def on_connect(self, **kwargs: typing.Any) -> None:
            assert self.ws["subprotocols"] == ["soap", "wamp"]
            await self.ws.accept(subprotocol="wamp")

    assert inspect.isawaitable(WebSocketEndpoint({"type": "websocket"}, None, None))

    client = client_factory(WsApp)
    with client.wsconnect("/ws", subprotocols=["soap", "wamp"]) as s:
        s.accepted_subprotocol == "wamp"


@pytest.mark.timeout(3)
def test_websocket_endpoint_on_receive_bytes(client_factory):
    class WsApp(WebSocketEndpoint):
        encoding = "bytes"

        async def on_receive(self, data) -> None:
            await self.send(b"Received msg is " + data)

        async def on_disconnect(self, code: int) -> None:
            pass

    client = client_factory(WsApp)
    with client.wsconnect("/ws") as s:
        msg = "Hello, Bytes"
        s.send_bytes(msg.encode("utf-8"))
        s.receive_bytes() == (f"Received msg is {msg}").encode("utf-8")


@pytest.mark.timeout(3)
def test_websocket_endpoint_on_receive_json(client_factory):
    class WsApp(WebSocketEndpoint):
        encoding = "json"

        async def on_receive(self, data) -> None:
            await self.send(data, send_type="json")

        async def on_disconnect(self, code: int) -> None:
            pass

    client = client_factory(WsApp)
    with client.wsconnect("/ws") as s:
        msg = {"json": {"hello": "json"}}
        s.send_json(msg)
        s.receive_json() == msg

        s.send_text('{"json": {"hello": "json"}}')
        s.receive_json() == msg

    with pytest.raises(RuntimeError) as exc:
        with client.wsconnect("/ws") as ss:
            ss.send_text('{"json": {"hello": "json"},}')
