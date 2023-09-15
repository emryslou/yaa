from yast import TestClient
from yast.formparsers import FormParser, UploadFile
from yast.requests import Request
from yast.responses import JSONResponse, Response


class ForceMultipartDict(dict):
    def __bool__(self):
        return True


FORCE_MULTIPART = ForceMultipartDict()


def app(scope):
    async def asgi(receive, send):
        req = Request(scope, receive)
        data = await req.form()
        output = {}
        for k, v in data.items():
            if isinstance(v, UploadFile):
                content = await v.read()
                output[k] = {"filename": v.filename, "content": content.decode()}
            else:
                output[k] = v
        await req.close()
        res = JSONResponse(output)
        await res(receive, send)

    return asgi


def test_formparsers_multipart_request_data(tmpdir):
    client = TestClient(app)
    res = client.get("/", data={"some": "data"}, files=FORCE_MULTIPART)
    assert res.json() == {"some": "data"}


def test_formparsers_multipart_request_files(tmpdir):
    import os

    path = os.path.join(tmpdir, "test.txt")
    with open(path, "wb") as f:
        f.write(b"<file content>")

    client = TestClient(app)
    res = client.get("/", files={"test": open(path, "rb")})
    assert res.json() == {
        "test": {
            "filename": "test.txt",
            "content": "<file content>",
        }
    }


def test_urlencoded_request_data(tmpdir):
    client = TestClient(app)
    response = client.post("/", data={"some": "data"})
    assert response.json() == {"some": "data"}


def test_no_request_data(tmpdir):
    client = TestClient(app)
    response = client.post("/")
    assert response.json() == {}


def test_multipart_request_multiple_files(tmpdir):
    import os

    path1 = os.path.join(tmpdir, "test1.txt")
    with open(path1, "wb") as file:
        file.write(b"<file1 content>")
    path2 = os.path.join(tmpdir, "test2.txt")
    with open(path2, "wb") as file:
        file.write(b"<file2 content>")
    client = TestClient(app)
    response = client.post(
        "/", files={"test1": open(path1, "rb"), "test2": open(path2, "rb")}
    )
    assert response.json() == {
        "test1": {"filename": "test1.txt", "content": "<file1 content>"},
        "test2": {"filename": "test2.txt", "content": "<file2 content>"},
    }


def test_multipart_request_mixed_files_and_data(tmpdir):
    client = TestClient(app)
    response = client.post(
        "/",
        data=(
            # data
            b"--a7f7ac8d4e2e437c877bb7b8d7cc549c\r\n"
            b'Content-Disposition: form-data; name="field0"\r\n\r\n'
            b"value0\r\n"
            # file
            b"--a7f7ac8d4e2e437c877bb7b8d7cc549c\r\n"
            b'Content-Disposition: form-data; name="file"; filename="file.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\n"
            b"<file content>\r\n"
            # data
            b"--a7f7ac8d4e2e437c877bb7b8d7cc549c\r\n"
            b'Content-Disposition: form-data; name="field1"\r\n\r\n'
            b"value1\r\n"
            b"--a7f7ac8d4e2e437c877bb7b8d7cc549c--\r\n"
        ),
        headers={
            "Content-Type": "multipart/form-data; boundary=a7f7ac8d4e2e437c877bb7b8d7cc549c"
        },
    )
    assert response.json() == {
        "file": {"filename": "file.txt", "content": "<file content>"},
        "field0": "value0",
        "field1": "value1",
    }
