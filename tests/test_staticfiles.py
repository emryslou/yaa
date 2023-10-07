import os
import typing
from email.utils import parsedate

import pytest

from yaa import TestClient, Yaa
from yaa.staticfiles import StaticFiles


def test_staticfiles(tmpdir):
    path = os.path.join(tmpdir, "example.txt")
    with open(path, "w") as file:
        file.write("<file content>")

    app = StaticFiles(directory=tmpdir)

    client = TestClient(app)

    res = client.get("/example.txt")
    assert res.status_code == 200
    assert res.text == "<file content>"

    res = client.post("/example.txt")
    assert res.status_code == 405
    assert res.text == "Method Not Allowed"

    res = client.get("/")
    assert res.status_code == 404
    assert res.text == "Not Found"

    res = client.get("/404.txt")
    assert res.status_code == 404
    assert res.text == "Not Found"

    res = client.get("/../../../example.txt")
    assert res.status_code == 200
    assert res.text == "<file content>"


def test_staticfiles_config_check_occurs_only_once(tmpdir):
    app = StaticFiles(directory=tmpdir)
    client = TestClient(app)
    assert not app.config_checked
    response = client.get("/")
    assert app.config_checked
    response = client.get("/")
    assert app.config_checked


def test_staticfiles_prevents_breaking_out_of_directory(tmpdir):
    from yaa.applications import Yaa

    directory = os.path.join(tmpdir, "foo")
    os.mkdir(directory)

    path = os.path.join(tmpdir, "example.txt")
    with open(path, "w") as file:
        file.write("outside root dir")

    app = Yaa()
    app.add_route("/", StaticFiles(directory=tmpdir))
    #    app = StaticFiles(directory=directory)
    client = TestClient(app)
    # We can't test this with 'requests', so we call the app directly here.
    response = client.get("/../example.txt")
    assert response.status_code == 404
    assert response.text == "Not Found"


def test_check_dir(tmpdir):
    import os

    with pytest.raises(AssertionError) as exc:
        StaticFiles(directory=os.path.join(tmpdir, "not_found"))
    assert "does not exist" in str(exc)

    StaticFiles(directory=os.path.join(tmpdir, "not_found"), check_dir=False)


def test_never_read_file_for_head_method(tmpdir):
    path = os.path.join(tmpdir, "ex.txt")
    with open(path, "w") as file:
        file.write("<file content>")

    app = StaticFiles(directory=tmpdir)
    client = TestClient(app)
    res = client.head("/ex.txt")
    assert res.status_code == 200
    assert res.content == b""


def test_304_with_etag_match(tmpdir):
    path = os.path.join(tmpdir, "ex1.txt")
    with open(path, "w") as f:
        f.write("<file content>")

    app = StaticFiles(directory=tmpdir)
    client = TestClient(app)

    res_1st = client.get("/ex1.txt")
    assert res_1st.status_code == 200
    assert "last-modified" in res_1st.headers
    assert "etag" in res_1st.headers

    res_2nd = client.get("/ex1.txt", headers={"if-none-match": res_1st.headers["etag"]})
    assert res_2nd.status_code == 304
    assert res_2nd.content == b""


def test_304_with_last_modified(tmpdir):
    import time

    path = os.path.join(tmpdir, "ex1.txt")

    file_last_modified_time = time.mktime(
        time.strptime("2013-10-10 23:40:00", "%Y-%m-%d %H:%M:%S")
    )

    with open(path, "w") as f:
        f.write("<file content>")

    os.utime(path, (file_last_modified_time, file_last_modified_time))

    app = StaticFiles(directory=tmpdir)
    client = TestClient(app)
    res = client.get(
        "/ex1.txt", headers={"If-Modified-Since": "Tue,11 Oct 2013 15:30:19 GMT"}
    )

    assert res.status_code == 304
    assert res.content == b""

    res = client.get(
        "/ex1.txt", headers={"If-Modified-Since": "Thu,20 Feb 2012 15:30:19 GMT"}
    )

    assert res.status_code == 200
    assert res.content == b"<file content>"


def test_staticfiles_with_package():
    app = StaticFiles(packages=["tests"])
    client = TestClient(app)
    response = client.get("/example.txt")
    assert response.status_code == 200
    assert response.text == "123\n"


def test_staticfiles_html(tmpdir):
    path = os.path.join(tmpdir, "404.html")
    with open(path, "w") as file:
        file.write("<h1>Custom not found page</h1>")
    path = os.path.join(tmpdir, "dir")
    os.mkdir(path)
    path = os.path.join(path, "index.html")
    with open(path, "w") as file:
        file.write("<h1>Hello</h1>")
    app = StaticFiles(directory=tmpdir, html=True)
    client = TestClient(app)
    response = client.get("/dir/")
    assert response.url == "http://testserver/dir/"
    assert response.status_code == 200
    assert response.text == "<h1>Hello</h1>"
    response = client.get("/dir")
    assert response.url == "http://testserver/dir/"
    assert response.status_code == 200
    assert response.text == "<h1>Hello</h1>"
    response = client.get("/dir/index.html")
    assert response.url == "http://testserver/dir/index.html"
    assert response.status_code == 200
    assert response.text == "<h1>Hello</h1>"
    response = client.get("/missing")
    assert response.status_code == 404
    assert response.text == "<h1>Custom not found page</h1>"


def test_staticfiles_head_with_middleware(tmpdir):
    from yaa.requests import Request
    from yaa.routing import Mount

    path = os.path.join(tmpdir, "example.txt")
    with open(path, "w") as file:
        file.write("x" * 100)
    routes = [
        Mount("/static", app=StaticFiles(directory=tmpdir), name="static"),
    ]
    app = Yaa(routes=routes)

    @app.middleware("http")
    async def does_nothing_middleware(request: Request, call_next):
        response = await call_next(request)
        return response

    client = TestClient(app)
    response = client.head("/static/example.txt", stream=True)
    assert response.status_code == 200
    # assert response.headers.get("content-length") == "100"


def test_staticfiles_with_pathlib(tmpdir):
    import pathlib

    base_dir = pathlib.Path(tmpdir)
    path = base_dir / "example.txt"
    with open(path, "w") as file:
        file.write("<file content>")
    app = StaticFiles(directory=base_dir)
    client = TestClient(app)
    response = client.get("/example.txt")
    assert response.status_code == 200
    assert response.text == "<file content>"


def test_staticfiles_cache_invalidation_for_deleted_file_html_mode(tmpdir):
    import time

    path_404 = os.path.join(tmpdir, "404.html")
    with open(path_404, "w") as file:
        file.write("<p>404 file</p>")
    path_some = os.path.join(tmpdir, "some.html")
    with open(path_some, "w") as file:
        file.write("<p>some file</p>")
    common_modified_time = time.mktime(
        time.strptime("2013-10-10 23:40:00", "%Y-%m-%d %H:%M:%S")
    )
    os.utime(path_404, (common_modified_time, common_modified_time))
    os.utime(path_some, (common_modified_time, common_modified_time))
    app = StaticFiles(directory=tmpdir, html=True)
    client = TestClient(app)
    resp_exists = client.get("/some.html")
    assert resp_exists.status_code == 200
    assert resp_exists.text == "<p>some file</p>"
    resp_cached = client.get(
        "/some.html",
        headers={"If-Modified-Since": resp_exists.headers["last-modified"]},
    )
    assert resp_cached.status_code == 304
    os.remove(path_some)
    resp_deleted = client.get(
        "/some.html",
        headers={"If-Modified-Since": resp_exists.headers["last-modified"]},
    )
    assert resp_deleted.status_code == 404
    assert resp_deleted.text == "<p>404 file</p>"
