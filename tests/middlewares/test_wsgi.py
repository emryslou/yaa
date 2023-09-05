import pytest
import sys

from yast.middlewares import WSGIMiddleware
from yast.middlewares.wsgi import build_environ
from yast.testclient import TestClient

def demo(environ, start_response):
    status = '200 OK'
    output = b'Hello Demo'
    headers = [
        ('Content-Type', 'text/plain; charser=utf-8'),
        ('Content-Length', str(len(output))),
    ]

    start_response(status, headers)
    return [output]

def echo_body(environ, start_response):
    status = "200 OK"
    output = environ["wsgi.input"].read()
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(output))),
    ]
    start_response(status, headers)
    return [output]


def raise_exception(environ, start_response):
    raise RuntimeError("Something went wrong")

def return_exc_info(environ, start_response):
    try:
        raise RuntimeError("Something went wrong")
    except:
        status = "500 Internal Server Error"
        output = b"Internal Server Error"
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(output))),
        ]
        start_response(status, headers, exc_info=sys.exc_info())
        return [output]



@pytest.mark.timeout(3)
def test_get():
    app = WSGIMiddleware(demo)
    client = TestClient(app)
    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'Hello Demo'

@pytest.mark.timeout(3)
def test_wsgi_post():
    app = WSGIMiddleware(echo_body)
    client = TestClient(app)
    response = client.post("/", json={"example": 123})
    assert response.status_code == 200
    assert response.text == '{"example": 123}'

@pytest.mark.timeout(3)
def test_wsgi_exception():
    # Note that we're testing the WSGI app directly here.
    # The HTTP protocol implementations would catch this error and return 500.
    app = WSGIMiddleware(raise_exception)
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        response = client.get("/")

@pytest.mark.timeout(3)
def test_wsgi_exc_info():
    # Note that we're testing the WSGI app directly here.
    # The HTTP protocol implementations would catch this error and return 500.
    app = WSGIMiddleware(return_exc_info)
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        response = client.get("/")
    app = WSGIMiddleware(return_exc_info)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


def test_build_environ():
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/",
        "query_string": b"a=123&b=456",
        "headers": [
            (b"host", b"www.example.org"),
            (b"content-type", b"application/json"),
            (b"content-length", b"18"),
            (b"accept", b"application/json"),
            (b"accept", b"text/plain"),
        ],
        "client": ("134.56.78.4", 1453),
        "server": ("www.example.org", 443),
    }
    body = b'{"example":"body"}'
    environ = build_environ(scope, body)
    stream = environ.pop("wsgi.input")
    assert stream.read() == b'{"example":"body"}'
    assert environ == {
        "CONTENT_LENGTH": "18",
        "CONTENT_TYPE": "application/json",
        "HTTP_ACCEPT": "application/json,text/plain",
        "HTTP_HOST": "www.example.org",
        "PATH_INFO": "/",
        "QUERY_STRING": "a=123&b=456",
        "REMOTE_ADDR": "134.56.78.4",
        "REQUEST_METHOD": "GET",
        "SCRIPT_NAME": "",
        "SERVER_NAME": "www.example.org",
        "SERVER_PORT": 443,
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.errors": sys.stdout,
        "wsgi.multiprocess": True,
        "wsgi.multithread": True,
        "wsgi.run_once": False,
        "wsgi.url_scheme": "https",
        "wsgi.version": (1, 0),
    }