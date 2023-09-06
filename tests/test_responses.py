import os

import pytest

from yast.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from yast.testclient import TestClient


def test_response_text():
    def app(scope):
        async def asgi(recv, send):
            response = Response("Hello, Response", media_type="text/plain")
            await response(recv, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.text == "Hello, Response"


def test_response_bytes():
    def app(scope):
        async def asgi(recv, send):
            response = Response(b"image/png", media_type="image/png")
            await response(recv, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.content == b"image/png"


def test_response_streaming():
    import asyncio

    def app(scope):
        async def numbers(minimum, maximum):
            for i in range(minimum, maximum + 1):
                yield str(i)
                if i != maximum:
                    yield ", "
                await asyncio.sleep(0)

        async def asgi(receive, send):
            generator = numbers(1, 5)
            response = StreamingResponse(generator, media_type="text/plain")
            await response(receive, send)

        return asgi

    client = TestClient(app)
    response = client.get("/")
    assert response.text == "1, 2, 3, 4, 5"


def test_response_headers():
    def app(scope):
        async def asgi(recv, send):
            headers = {"x-header-1": "123", "x-header-2": "234"}
            response = Response(
                "Hello, Response", media_type="text/plain", headers=headers
            )
            await response(recv, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.headers["x-header-1"] == "123"
    assert res.headers["x-header-2"] == "234"


def test_streaming_response_headers():
    def app(scope):
        async def asgi(receive, send):
            async def stream(msg):
                yield "hello, world"

            headers = {"x-header-1": "123", "x-header-2": "456"}
            response = StreamingResponse(
                stream("hello, world"), media_type="text/plain", headers=headers
            )
            response.headers["x-header-2"] = "789"
            await response(receive, send)

        return asgi

    client = TestClient(app)
    response = client.get("/")
    assert response.headers["x-header-1"] == "123"
    assert response.headers["x-header-2"] == "789"


def test_file_response(tmpdir):
    content = b"<file content>" * 1000
    path = os.path.join(tmpdir, "xyz")
    with open(path, "wb") as file:
        file.write(content)

    def app(scope):
        return FileResponse(path=path, filename="example.png")

    client = TestClient(app)

    res = client.get("/")
    assert res.status_code == 200
    assert res.content == content
    assert res.headers["content-type"] == "image/png"
    assert res.headers["content-disposition"] == 'attachment; filename="example.png"'
    assert "content-length" in res.headers


def test_redirect():
    def app(scope):
        async def asgi(receive, send):
            if scope["path"] == "/":
                response = Response("hello, world", media_type="text/plain")
            else:
                response = RedirectResponse("/")
            await response(receive, send)

        return asgi

    client = TestClient(app)
    response = client.get("/redirect")
    assert response.text == "hello, world"
    assert response.url == "http://testserver/"


def test_phrase():
    def app(scope):
        return Response(b"", status_code=200)

    client = TestClient(app)
    res = client.get("/")
    assert res.reason == "OK"

    def app(scope):
        return Response(b"", status_code=123)

    client = TestClient(app)
    res = client.get("/")
    assert res.reason == ""

    def app(scope):
        return Response(b"", status_code=500)

    client = TestClient(app)
    res = client.get("/")
    assert res.reason == "Internal Server Error"


def test_set_cookie():
    def app(scope):
        async def asgi(receive, send):
            res = Response("Hello, Set Cookie")
            res.set_cookie("my_cookie", "AAAAA")
            await res(receive, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.text == "Hello, Set Cookie"
    assert "my_cookie" in res.cookies
    assert res.cookies.get("my_cookie") == "AAAAA"


def test_del_cookie():
    from yast.requests import Request

    def app(scope):
        async def asgi(receive, send):
            req = Request(scope, receive)
            res = Response("Hello, Set Cookie")
            if req.cookie.get("my_cookie"):
                res.del_cookie("my_cookie")
            else:
                res.set_cookie("my_cookie", "AAAAA")
            await res(receive, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.text == "Hello, Set Cookie"
    assert "my_cookie" in res.cookies
    assert res.cookies.get("my_cookie") == "AAAAA"

    res = client.get("/")
    assert res.text == "Hello, Set Cookie"
    assert "my_cookie" not in res.cookies


def test_response_ujson():
    from yast.responses import UJSONResponse

    def app(scope):
        async def asgi(receive, send):
            res = UJSONResponse({"hello": "usjon"})
            await res(receive, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.json() == {"hello": "usjon"}


def test_file_response_with_directory_raises_error(tmpdir):
    def app(scope):
        return FileResponse(path=tmpdir, filename="example.png")

    client = TestClient(app)
    with pytest.raises(RuntimeError) as exc:
        client.get("/")
    assert "is not a file" in str(exc)


def test_file_response_with_missing_file_raises_error(tmpdir):
    path = os.path.join(tmpdir, "404.txt")

    def app(scope):
        return FileResponse(path=path, filename="404.txt")

    client = TestClient(app)
    with pytest.raises(RuntimeError) as exc:
        client.get("/")
    assert "does not exist" in str(exc)
