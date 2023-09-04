from yast.applications import Yast
from yast.middlewares import GZipMiddleware
from yast.responses import PlainTextResponse, StreamingResponse
from yast.testclient import TestClient


def test_gzip_responses():
    app = Yast()
    app.add_middleware(GZipMiddleware)
    @app.route("/")
    def homepage(request):
        return PlainTextResponse("x" * 4000, status_code=200)
    
    client = TestClient(app)
    response = client.get("/", headers={"accept-encoding": "gzip"})
    assert response.status_code == 200
    assert response.text == "x" * 4000
    assert response.headers["content-encoding"] == "gzip"
    assert int(response.headers["content-length"]) < 4000

def test_gzip_not_in_accept_encoding():
    app = Yast()
    app.add_middleware(GZipMiddleware)
    @app.route("/")
    def homepage(request):
        return PlainTextResponse("x" * 4000, status_code=200)
    client = TestClient(app)
    response = client.get("/", headers={"accept-encoding": "identity"})
    assert response.status_code == 200
    assert response.text == "x" * 4000
    assert "Content-Encoding" not in response.headers
    assert int(response.headers["Content-Length"]) == 4000

def test_gzip_ignored_for_small_responses():
    app = Yast()
    app.add_middleware(GZipMiddleware)
    @app.route("/")
    def homepage(request):
        return PlainTextResponse("OK", status_code=200)
    client = TestClient(app)
    response = client.get("/", headers={"accept-encoding": "gzip"})
    assert response.status_code == 200
    assert response.text == "OK"
    assert "Content-Encoding" not in response.headers
    assert int(response.headers["Content-Length"]) == 2
    
def test_gzip_streaming_response():
    app = Yast()
    app.add_middleware(GZipMiddleware)
    @app.route("/")
    def homepage(request):
        async def generator(bytes, count):
            for index in range(count):
                yield bytes
        streaming = generator(bytes=b"x" * 400, count=10)
        return StreamingResponse(streaming, status_code=200)
    client = TestClient(app)
    response = client.get("/", headers={"accept-encoding": "gzip"})
    assert response.status_code == 200
    assert response.text == "x" * 4000
    assert response.headers["Content-Encoding"] == "gzip"
    assert "Content-Length" not in response.headers