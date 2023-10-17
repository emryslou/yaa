import pytest

import yaa.status as status
from yaa.websockets import WebSocket, WebSocketDisconnect, WebSocketState


def test_websocket_url(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        await session.send_json({"url": str(session.url)})
        await session.close()

    client = client_factory(app)
    with client.wsconnect("/aaa?b=ccc") as ss:
        data = ss.receive_json()
        assert data == {"url": "ws://testserver/aaa?b=ccc"}


def test_websocket_query_params(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        await session.send_json({"params": dict(session.query_params)})
        await session.close()

    client = client_factory(app)
    with client.wsconnect("/aaa?b=ccc&d=22&ff=sss") as ss:
        data = ss.receive_json()
        assert data == {"params": {"b": "ccc", "d": "22", "ff": "sss"}}


def test_websocket_headers(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        await session.send_json({"headers": dict(session.headers)})
        await session.close()

    client = client_factory(app)
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


def test_websocket_port(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        await session.send_json({"port": session.url.port})
        await session.close()

    client = client_factory(app)
    with client.wsconnect("ws://www.example.com:123/a?cc=cc") as ss:
        data = ss.receive_json()

        assert data == {"port": 123}


def test_websocket_send_and_receive_text(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        data = await session.receive_text()
        await session.send_text("Message was: " + data)
        await session.close()

    client = client_factory(app)
    with client.wsconnect("/") as session:
        session.send_text("Hello, world!")
        data = session.receive_text()
        assert data == "Message was: Hello, world!"


def test_websocket_send_and_receive_bytes(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        data = await session.receive_bytes()
        await session.send_bytes(b"Message was: " + data)
        await session.close()

    client = client_factory(app)
    with client.wsconnect("/") as session:
        session.send_bytes(b"Hello, bytes!")
        data = session.receive_bytes()
        assert data == b"Message was: Hello, bytes!"


def test_websocket_send_and_receive_json(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        data = await session.receive_json()
        await session.send_bytes({"json": data})
        await session.close()

    client = client_factory(app)
    with client.wsconnect("/") as session:
        session.send_json({"hello": "json"})
        data = session.receive_bytes()
        assert data == {"json": {"hello": "json"}}


def test_client_close(client_factory):
    close_code = None

    async def app(scope, receive, send):
        nonlocal close_code
        session = WebSocket(scope, receive, send)
        await session.accept()
        try:
            data = await session.receive_text()
        except WebSocketDisconnect as exc:
            close_code = exc.code

    client = client_factory(app)
    with client.wsconnect("/") as session:
        session.close(code=status.WS_1001_GOING_AWAY)
    assert close_code == status.WS_1001_GOING_AWAY


def test_application_close(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        await session.close(status.WS_1001_GOING_AWAY)

    client = client_factory(app)
    with client.wsconnect("/") as session:
        with pytest.raises(WebSocketDisconnect) as exc:
            session.receive_text()
        assert exc.value.code == status.WS_1001_GOING_AWAY


def test_rejected_connection(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.close(status.WS_1008_POLICY_VIOLATION)

    client = client_factory(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.wsconnect("/"):
            pass
    assert exc.value.code == status.WS_1008_POLICY_VIOLATION


def test_subprotocol(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        assert session["subprotocols"] == ["soap", "wamp"]
        await session.accept(subprotocol="wamp")
        await session.close()

    client = client_factory(app)
    with client.wsconnect("/", subprotocols=["soap", "wamp"]) as session:
        assert session.accepted_subprotocol == "wamp"


def test_websocket_exception(client_factory):
    async def app(scope, receive, send):
        assert False

    client = client_factory(app)
    with pytest.raises(AssertionError):
        with client.wsconnect("/123?a=abc"):
            pass


def test_duplicate_close(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        await session.close()
        await session.close()

    client = client_factory(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/") as session:
            pass


def test_duplicate_disconnect(client_factory):
    async def app(scope, receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        message = await session.receive()
        assert message["type"] == "websocket.disconnect"
        message = await session.receive()

    client = client_factory(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/") as session:
            session.close()


def test_websocket_scope_interface(client_factory):
    """
    A WebSocket can be instantiated with a scope, and presents a `Mapping`
    interface.
    """
    session = WebSocket({"type": "websocket", "path": "/abc/", "headers": []})
    assert session["type"] == "websocket"
    assert dict(session) == {"type": "websocket", "path": "/abc/", "headers": []}
    assert len(session) == 3


def test_websocket_iter_text(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            async for data in websocket.iter_text():
                await websocket.send_text("Message was: " + data)

        return asgi

    client = client_factory(app)
    with client.wsconnect("/") as websocket:
        websocket.send_text("Hello, world!")
        data = websocket.receive_text()
        assert data == "Message was: Hello, world!"


def test_websocket_iter_bytes(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            async for data in websocket.iter_bytes():
                await websocket.send_bytes(b"Message was: " + data)

        return asgi

    client = client_factory(app)
    with client.wsconnect("/") as websocket:
        websocket.send_bytes(b"Hello, world!")
        data = websocket.receive_bytes()
        assert data == b"Message was: Hello, world!"


def test_websocket_iter_json(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            async for data in websocket.iter_json():
                await websocket.send_json({"message": data})

        return asgi

    client = client_factory(app)
    with client.wsconnect("/") as websocket:
        websocket.send_json({"hello": "world"})
        data = websocket.receive_json()
        assert data == {"message": {"hello": "world"}}


def test_websocket_concurrency_pattern(no_trio_support, client_factory):
    import asyncio
    from yaa.concurrency import run_until_first_complete

    def app(scope):
        async def reader(websocket, queue):
            async for data in websocket.iter_json():
                await queue.put(data)

        async def writer(websocket, queue):
            while True:
                message = await queue.get()
                await websocket.send_json(message)

        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            queue = asyncio.Queue()
            await websocket.accept()
            await run_until_first_complete(
                (reader, {"websocket": websocket, "queue": queue}),
                (writer, {"websocket": websocket, "queue": queue}),
            )
            await websocket.close()

        return asgi

    client = client_factory(app)
    with client.wsconnect("/") as websocket:
        websocket.send_json({"hello": "world"})
        data = websocket.receive_json()
        assert data == {"hello": "world"}


def test_additional_headers(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept(headers=[(b"additional", b"header")])
            await websocket.close()

        return asgi

    client = client_factory(app)
    with client.wsconnect("/") as websocket:
        assert websocket.extra_headers == [(b"additional", b"header")]


def test_no_additional_headers(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            await websocket.close()

        return asgi

    client = client_factory(app)
    with client.wsconnect("/") as websocket:
        assert websocket.extra_headers == []


def test_websocket_close_reason(client_factory) -> None:
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            await websocket.close(code=status.WS_1001_GOING_AWAY, reason="Going Away")

        return asgi

    client = client_factory(app)
    with client.wsconnect("/") as websocket:
        with pytest.raises(WebSocketDisconnect) as exc:
            websocket.receive_text()
        assert exc.value.code == status.WS_1001_GOING_AWAY
        assert exc.value.reason == "Going Away"


def test_receive_text_before_accept(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.receive_text()

        return asgi

    client = client_factory(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/"):
            pass  # pragma: nocover


def test_receive_bytes_before_accept(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.receive_bytes()

        return asgi

    client = client_factory(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/"):
            pass  # pragma: nocover


def test_receive_json_before_accept(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.receive_json()

        return asgi

    client = client_factory(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/"):
            pass  # pragma: nocover


def test_send_before_accept(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.send({"type": "websocket.send"})

        return asgi

    client = client_factory(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/"):
            pass  # pragma: nocover


def test_send_wrong_message_type(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.send({"type": "websocket.accept"})
            await websocket.send({"type": "websocket.accept"})

        return asgi

    client = client_factory(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/"):
            pass  # pragma: nocover


def test_receive_before_accept(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            websocket.client_state = WebSocketState.CONNECTING
            await websocket.receive()

        return asgi

    client = client_factory(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/") as websocket:
            websocket.send({"type": "websocket.send"})


def test_receive_wrong_message_type(client_factory):
    def app(scope):
        async def asgi(receive, send):
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            await websocket.receive()

        return asgi

    client = client_factory(app)
    with pytest.raises(RuntimeError):
        with client.wsconnect("/") as websocket:
            websocket.send({"type": "websocket.connect"})


def test_raise_exc(client_factory):
    import anyio
    from yaa.applications import Yaa
    from yaa.exceptions import WebSocketException

    class CustomWSException(Exception):
        pass

    def custom_ws_exception_handler(websocket: WebSocket, exc: CustomWSException):
        anyio.from_thread.run(websocket.close, status.WS_1013_TRY_AGAIN_LATER)

    app = Yaa(exception_handlers={CustomWSException: custom_ws_exception_handler})

    @app.ws_route("/ws-raise-customexc")
    async def websocket_raise_custom(websocket: WebSocket):
        await websocket.accept()
        raise CustomWSException()

    @app.ws_route("/ws-raise-wsexc")
    async def websocket_raise_websocket(websocket: WebSocket):
        await websocket.accept()
        raise WebSocketException(code=status.WS_1003_UNSUPPORTED_DATA)

    client = client_factory(app)

    with client.wsconnect("/ws-raise-wsexc") as session:
        response = session.receive()
        assert response == {
            "type": "websocket.close",
            "code": status.WS_1003_UNSUPPORTED_DATA,
            "reason": "",
        }

    with client.wsconnect("/ws-raise-customexc") as session:
        response = session.receive()
        assert response == {
            "type": "websocket.close",
            "code": status.WS_1013_TRY_AGAIN_LATER,
            "reason": "",
        }
