import asyncio

import pytest

from yast import TestClient
from yast.requests import ClientDisconnect, Request
from yast.responses import JSONResponse


class ForceMultipartDict(dict):
    def __bool__(self):
        return True


FORCE_MULTIPART = ForceMultipartDict()


def test_request_url():
    """test"""

    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            data = {"method": request.method, "url": str(request.url)}
            response = JSONResponse(data)
            await response(recv, send)

        return asgi

    client = TestClient(app)
    res = client.get("/path/to/page?a=abc")
    assert res.json() == {
        "method": "GET",
        "url": "http://testserver/path/to/page?a=abc",
    }


def test_request_query_params():
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            data = {"params": dict(request.query_params)}
            response = JSONResponse(data)
            await response(recv, send)

        return asgi

    client = TestClient(app)
    res = client.get("/path/to/page?a=abc")
    assert res.json() == {"params": {"a": "abc"}}


def test_request_headers():
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            response = JSONResponse({"headers": dict(request.headers)})
            await response(recv, send)

        return asgi

    client = TestClient(app)
    res = client.get("/path/to/page?a=abc", headers={"host": "abc.com"})
    assert res.json() == {
        "headers": {
            "user-agent": "testclient",
            "host": "abc.com",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate",
            "connection": "keep-alive",
        }
    }


def test_request_body():
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            body = await request.body()
            response = JSONResponse({"body": body.decode()})
            await response(recv, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.json() == {"body": ""}

    res = client.post("/", json={"a": "123"})
    assert res.json() == {"body": '{"a": "123"}'}

    res = client.post("/", data="aaa")
    assert res.json() == {"body": "aaa"}


def test_request_json():
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            body = await request.json()
            response = JSONResponse({"json": body})
            await response(recv, send)

        return asgi

    client = TestClient(app)

    res = client.post("/", json={"a": "123"})
    assert res.json() == {"json": {"a": "123"}}


def test_request_stream():
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            body = b""
            async for chunk in request.stream():
                body += chunk
            response = JSONResponse({"body": body.decode()})
            await response(recv, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.json() == {"body": ""}

    res = client.post("/", json={"a": "123"})
    assert res.json() == {"body": '{"a": "123"}'}

    res = client.post("/", data="1234")
    assert res.json() == {"body": "1234"}


def test_request_body_then_stream():
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)

            body = await request.body()

            chunks = b""
            async for chunk in request.stream():
                chunks += chunk
            response = JSONResponse({"body": body.decode(), "stream": chunks.decode()})
            await response(recv, send)

        return asgi

    client = TestClient(app)
    res = client.post("/", data="1234")
    assert res.json() == {"body": "1234", "stream": "1234"}


def test_request_body_then_stream_err():
    """ """

    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            chunks = b""
            async for chunk in request.stream():
                chunks += chunk
            try:
                body = await request.body()
            except RuntimeError:
                body = b"<stream consumed>"
            response = JSONResponse({"body": body.decode(), "stream": chunks.decode()})
            await response(recv, send)

        return asgi

    client = TestClient(app)
    res = client.post("/", data="1234")
    assert res.json() == {"body": "<stream consumed>", "stream": "1234"}


def test_quest_relative_url():
    def app(scope):
        async def asgi(recv, send):
            req = Request(scope, recv)
            data = {"method": req.method, "relative_url": req.relative_url}
            res = JSONResponse(data)
            await res(recv, send)

        return asgi

    client = TestClient(app)

    res = client.get("/123?a=abc")
    assert res.json() == {"method": "GET", "relative_url": "/123?a=abc"}

    res = client.get("https://exmaple.org:123/")
    assert res.json() == {"method": "GET", "relative_url": "/"}


def test_request_disconnect():
    def app(scope):
        async def asgi(recv, send):
            req = Request(scope, recv)
            await req.body()

        return asgi

    async def rev(*args, **kwargs):
        return {"type": "http.disconnect"}

    scope = {"method": "POST", "path": "/"}

    asgi_call = app(scope)

    loop = asyncio.get_event_loop()
    with pytest.raises(ClientDisconnect):
        loop.run_until_complete(asgi_call(rev, None))
        assert True == 1


def test_request_cookies():
    from yast.responses import PlainTextResponse, Response

    def app(scope):
        async def asgi(receive, send):
            req = Request(scope, receive)
            mycookie = req.cookie.get("my_cookie")
            if mycookie:
                res = PlainTextResponse(mycookie)
            else:
                res = PlainTextResponse("Hello, NoCookies")
                res.set_cookie("my_cookie", "cooooooooooooookies")
            await res(receive, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.text == "Hello, NoCookies"

    res = client.get(
        "/",
    )
    assert res.text == "cooooooooooooookies"


def test_chunked_encoding():
    def app(scope):
        async def asgi(receive, send):
            request = Request(scope, receive)
            body = await request.body()
            response = JSONResponse({"body": body.decode()})
            await response(receive, send)

        return asgi

    client = TestClient(app)

    def post_body():
        yield b"foo"
        yield "bar"

    response = client.post("/", data=post_body())
    assert response.json() == {"body": "foobar"}


def test_request_client():
    def app(scope):
        async def asgi(receive, send):
            request = Request(scope, receive)
            response = JSONResponse(
                {"host": request.client.host, "port": request.client.port}
            )
            await response(receive, send)

        return asgi

    client = TestClient(app)
    response = client.get("/")
    assert response.json() == {"host": "testclient", "port": 50000}


def app_read_body(scope):
    async def asgi(receive, send):
        request = Request(scope, receive)
        # Read bytes, to force request.stream() to return the already parsed body
        body_bytes = await request.body()
        data = await request.form()
        output = {}
        for key, value in data.items():
            output[key] = value
        await request.close()
        response = JSONResponse(output)
        await response(receive, send)

    return asgi


def test_urlencoded_multi_field_app_reads_body(tmpdir):
    client = TestClient(app_read_body)
    response = client.post("/", data={"some": "data", "second": "key pair"})
    assert response.json() == {"some": "data", "second": "key pair"}


def test_multipart_multi_field_app_reads_body(tmpdir):
    client = TestClient(app_read_body)
    response = client.post(
        "/", data={"some": "data", "second": "key pair"}, files=FORCE_MULTIPART
    )
    assert response.json() == {"some": "data", "second": "key pair"}


def test_request_is_disconnected():
    """
    If a client disconnect occurs while reading request body
    then ClientDisconnect should be raised.
    """
    disconnected_after_response = None

    def app(scope):
        async def asgi(receive, send):
            nonlocal disconnected_after_response
            request = Request(scope, receive)
            await request.body()
            disconnected = await request.is_disconnected()
            response = JSONResponse({"disconnected": disconnected})
            await response(receive, send)
            disconnected_after_response = await request.is_disconnected()

        return asgi

    client = TestClient(app)
    response = client.get("/")
    assert response.json() == {"disconnected": False}
    assert disconnected_after_response


def test_request_state():
    def app(scope):
        async def asgi(receive, send):
            request = Request(scope, receive)
            request.state.example = "abc"
            response = JSONResponse({"state.example": request["state"].example})
            await response(receive, send)

        return asgi

    client = TestClient(app)
    response = client.get("/123?a=abc")
    assert response.json() == {"state.example": "abc"}
