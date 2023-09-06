import pytest

import yast.status as status
from yast import TestClient
from yast.websockets import WebSocket, WebSocketDisconnect


class test_websocket_url:
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.accept()
            await session.send_json({"url": str(session.url)})
            await session.close()

        return asgi

    client = TestClient(app)
    with client.wsconnect("/aaa?b=ccc") as ss:
        data = ss.receive_json()
        assert data == {"url": "ws://testserver/aaa?b=ccc"}


class test_websocket_query_params:
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.accept()
            await session.send_json({"params": dict(session.query_params)})
            await session.close()

        return asgi

    client = TestClient(app)
    with client.wsconnect("/aaa?b=ccc&d=22&ff=sss") as ss:
        data = ss.receive_json()
        assert data == {"params": {"b": "ccc", "d": "22", "ff": "sss"}}


class test_websocket_headers:
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.accept()
            await session.send_json({"headers": dict(session.headers)})
            await session.close()

        return asgi

    client = TestClient(app)
    with client.wsconnect("/aaa?b=ccc&d=22&ff=sss") as ss:
        data = ss.receive_json()
        expected_headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate",
            "connection": "upgrade",
            "host": "testserver",
            "user-agent": "testclient",
            "sec-websocket-key": "testserver==",
            "sec-websocket-version": "13",
        }
        assert data == {"headers": expected_headers}


class test_websocket_headers:
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.accept()
            await session.send_json({"port": session.url.port})
            await session.close()

        return asgi

    client = TestClient(app)
    with client.wsconnect("ws://www.example.com:123/a?cc=cc") as ss:
        data = ss.receive_json()

        assert data == {"port": 123}


def test_websocket_send_and_receive_text():
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.accept()
            data = await session.receive_text()
            await session.send_text("Message was: " + data)
            await session.close()

        return asgi

    client = TestClient(app)
    with client.wsconnect("/") as session:
        session.send_text("Hello, world!")
        data = session.receive_text()
        assert data == "Message was: Hello, world!"


def test_websocket_send_and_receive_bytes():
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.accept()
            data = await session.receive_bytes()
            await session.send_bytes(b"Message was: " + data)
            await session.close()

        return asgi

    client = TestClient(app)
    with client.wsconnect("/") as session:
        session.send_bytes(b"Hello, bytes!")
        data = session.receive_bytes()
        assert data == b"Message was: Hello, bytes!"


def test_websocket_send_and_receive_json():
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.accept()
            data = await session.receive_json()
            await session.send_bytes({"json": data})
            await session.close()

        return asgi

    client = TestClient(app)
    with client.wsconnect("/") as session:
        session.send_json({"hello": "json"})
        data = session.receive_bytes()
        assert data == {"json": {"hello": "json"}}


def test_client_close():
    close_code = None

    def app(scope):
        async def asgi(receive, send):
            nonlocal close_code
            session = WebSocket(scope, receive, send)
            await session.accept()
            try:
                data = await session.receive_text()
            except WebSocketDisconnect as exc:
                close_code = exc.code

        return asgi

    client = TestClient(app)
    with client.wsconnect("/") as session:
        session.close(code=status.WS_1001_GOING_AWAY)
    assert close_code == status.WS_1001_GOING_AWAY


def test_application_close():
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.accept()
            await session.close(status.WS_1001_GOING_AWAY)

        return asgi

    client = TestClient(app)
    with client.wsconnect("/") as session:
        with pytest.raises(WebSocketDisconnect) as exc:
            session.receive_text()
        assert exc.value.code == status.WS_1001_GOING_AWAY


def test_rejected_connection():
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.close(status.WS_1008_POLICY_VIOLATION)

        return asgi

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        client.wsconnect("/")
    assert exc.value.code == status.WS_1008_POLICY_VIOLATION


def test_subprotocol():
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            assert session["subprotocols"] == ["soap", "wamp"]
            await session.accept(subprotocol="wamp")
            await session.close()

        return asgi

    client = TestClient(app)
    with client.wsconnect("/", subprotocols=["soap", "wamp"]) as session:
        assert session.accepted_subprotocol == "wamp"


def test_websocket_exception():
    def app(scope):
        async def asgi(receive, send):
            assert False

        return asgi

    client = TestClient(app)
    with pytest.raises(AssertionError):
        client.wsconnect("/123?a=abc")


def test_duplicate_close():
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.accept()
            await session.close()
            await session.close()

        return asgi

    client = TestClient(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/") as session:
            pass


def test_duplicate_disconnect():
    def app(scope):
        async def asgi(receive, send):
            session = WebSocket(scope, receive, send)
            await session.accept()
            message = await session.receive()
            assert message["type"] == "websocket.disconnect"
            message = await session.receive()

        return asgi

    client = TestClient(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/") as session:
            session.close()


def test_websocket_scope_interface():
    """
    A WebSocket can be instantiated with a scope, and presents a `Mapping`
    interface.
    """
    session = WebSocket({"type": "websocket", "path": "/abc/", "headers": []})
    assert session["type"] == "websocket"
    assert dict(session) == {"type": "websocket", "path": "/abc/", "headers": []}
    assert len(session) == 3
