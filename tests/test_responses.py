import asyncio
import os

import pytest

from yast.background import BackgroundTask
from yast.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from yast.testclient import TestClient


def test_response_text():
    filled_by_bg_task = ""

    async def numbers(min, max):
        for i in range(min, max + 1):
            yield str(i)
            if i != max:
                yield ","
            await asyncio.sleep(0)

    async def numbers_for_cleanup(start=1, stop=5):
        nonlocal filled_by_bg_task
        async for thing in numbers(start, stop):
            filled_by_bg_task = filled_by_bg_task + thing

    cleanup_task = BackgroundTask(numbers_for_cleanup, start=6, stop=9)

    async def app(scope, recv, send):
        genrator = numbers(1, 5)
        response = StreamingResponse(
            genrator, media_type="text/plain", background=cleanup_task
        )
        await response(scope, recv, send)

    assert filled_by_bg_task == ""
    client = TestClient(app)
    res = client.get("/")
    assert res.text == "1,2,3,4,5"
    assert filled_by_bg_task == "6,7,8,9"


def test_response_bytes():
    async def app(scope, recv, send):
        response = Response(b"image/png", media_type="image/png")
        await response(scope, recv, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.content == b"image/png"


def test_response_streaming():
    import asyncio

    async def numbers(minimum, maximum):
        for i in range(minimum, maximum + 1):
            yield str(i)
            if i != maximum:
                yield ", "
            await asyncio.sleep(0)

    async def app(scope, receive, send):
        generator = numbers(1, 5)
        response = StreamingResponse(generator, media_type="text/plain")
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/")
    assert response.text == "1, 2, 3, 4, 5"


def test_response_headers():
    async def app(scope, recv, send):
        headers = {"x-header-1": "123", "x-header-2": "234"}
        response = Response("Hello, Response", media_type="text/plain", headers=headers)
        await response(scope, recv, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.headers["x-header-1"] == "123"
    assert res.headers["x-header-2"] == "234"


def test_streaming_response_headers():
    async def app(scope, receive, send):
        async def stream(msg):
            yield "hello, world"

        headers = {"x-header-1": "123", "x-header-2": "456"}
        response = StreamingResponse(
            stream("hello, world"), media_type="text/plain", headers=headers
        )
        response.headers["x-header-2"] = "789"
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/")
    assert response.headers["x-header-1"] == "123"
    assert response.headers["x-header-2"] == "789"


def test_file_response(tmpdir):
    content = b"<file content>" * 1000
    path = os.path.join(tmpdir, "xyz")
    with open(path, "wb") as file:
        file.write(content)

    filled_by_bg_task = ""

    async def numbers(minimum, maximum):
        for i in range(minimum, maximum + 1):
            yield str(i)
            if i != maximum:
                yield ","
            await asyncio.sleep(0)

    async def numbers_for_cleanup(start=1, stop=5):
        nonlocal filled_by_bg_task
        async for thing in numbers(start, stop):
            filled_by_bg_task = filled_by_bg_task + thing

    cleanup_task = BackgroundTask(numbers_for_cleanup, start=6, stop=9)

    async def app(scope, receive, send):
        await FileResponse(path=path, filename="example.png", background=cleanup_task)(
            scope, receive, send
        )

    client = TestClient(app)

    res = client.get("/")
    assert res.status_code == 200
    assert res.content == content
    assert res.headers["content-type"] == "image/png"
    assert res.headers["content-disposition"] == 'attachment; filename="example.png"'
    assert "content-length" in res.headers
    assert filled_by_bg_task == "6,7,8,9"


def test_redirect():
    async def app(scope, receive, send):
        if scope["path"] == "/":
            response = Response("hello, world", media_type="text/plain")
        else:
            response = RedirectResponse("/")
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/redirect")
    assert response.text == "hello, world"
    assert response.url == "http://testserver/"


def test_phrase():
    async def app(scope, receive, send):
        await Response(b"", status_code=200)(scope, receive, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.reason == "OK"

    async def app(scope, receive, send):
        await Response(b"", status_code=123)(scope, receive, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.reason == ""

    async def app(scope, receive, send):
        await Response(b"", status_code=500)(scope, receive, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.reason == "Internal Server Error"


def test_set_cookie():
    async def app(scope, receive, send):
        res = Response("Hello, Set Cookie", media_type="text/plain")
        res.set_cookie(
            key="my_cookie",
            value="AAAAA",
            max_age=10,
            expires=10,
            path="/",
            domain="localhost",
            secure=True,
            httponly=True,
            samesite="none",
        )
        await res(scope, receive, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.text == "Hello, Set Cookie"
    assert "set-cookie" in res.headers
    cookies = res.headers.get("set-cookie")
    assert cookies.count("my_cookie=AAAAA") == 1
    assert cookies.count("Domain=localhost") == 1
    assert cookies.count("HttpOnly;") == 1


def test_del_cookie():
    from yast.requests import Request

    async def app(scope, receive, send):
        req = Request(scope, receive)
        res = Response("Hello, Set Cookie")
        if req.cookies.get("my_cookie"):
            res.del_cookie("my_cookie")
        else:
            res.set_cookie("my_cookie", "AAAAA")
        await res(scope, receive, send)

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

    async def app(scope, receive, send):
        res = UJSONResponse({"hello": "usjon"})
        await res(scope, receive, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.json() == {"hello": "usjon"}


def test_file_response_with_directory_raises_error(tmpdir):
    async def app(scope, receive, send):
        await FileResponse(path=tmpdir, filename="example.png")(scope, receive, send)

    client = TestClient(app)
    with pytest.raises(RuntimeError) as exc:
        client.get("/")
    assert "is not a file" in str(exc)


def test_file_response_with_missing_file_raises_error(tmpdir):
    path = os.path.join(tmpdir, "404.txt")

    async def app(scope, receive, send):
        await FileResponse(path=path, filename="404.txt")(scope, receive, send)

    client = TestClient(app)
    with pytest.raises(RuntimeError) as exc:
        client.get("/")
    assert "does not exist" in str(exc)


def test_response_no_content():
    async def app(scope, receive, send):
        await Response()(scope, receive, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == ""


def test_form_urlencode():
    from yast.requests import Request
    from yast.responses import JSONResponse

    async def app(scope, rec, send):
        req = Request(scope=scope, receive=rec)
        body = b""
        form = await req.form()
        res = JSONResponse({"form": dict(form)})
        await res(scope, receive=rec, send=send)

    client = TestClient(app)

    res = client.post("/")
    assert res.json() == {"form": {}}

    res = client.post("/", data={"abc": "123 @ aaa"})
    assert res.json() == {"form": {"abc": "123 @ aaa"}}


def test_json_none_response():
    from yast.responses import JSONResponse

    async def app(scope, receive, send):
        response = JSONResponse(None)
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/")
    assert response.json() is None


def test_file_response_with_chinese_filename(tmpdir):
    content = b"file content"
    filename = "你好.txt"  # probably "Hello.txt" in Chinese
    path = os.path.join(tmpdir, filename)
    with open(path, "wb") as f:
        f.write(content)
    app = FileResponse(path=path, filename=filename)
    client = TestClient(app)
    response = client.get("/")
    expected_disposition = "attachment; filename*=utf-8''%E4%BD%A0%E5%A5%BD.txt"
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-disposition"] == expected_disposition
