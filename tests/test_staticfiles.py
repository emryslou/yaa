import os

import pytest

from yast import TestClient
from yast.staticfiles import StaticFiles


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
    directory = os.path.join(tmpdir, "foo")
    os.mkdir(directory)

    path = os.path.join(tmpdir, "example.txt")
    with open(path, "w") as file:
        file.write("outside root dir")

    app = StaticFiles(directory=directory)
    # We can't test this with 'requests', so we call the app directly here.
    response = app({"type": "http", "method": "GET", "path": "/../example.txt"})
    assert response.status_code == 404
    assert response.body == b"Not Found"


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
