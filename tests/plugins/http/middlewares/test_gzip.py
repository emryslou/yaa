from yaa.applications import Yaa
from yaa.responses import PlainTextResponse, StreamingResponse


def test_gzip_responses(client_factory):
    app = Yaa(plugins={"http": {"middlewares": {"gzip": {}}}})

    @app.route("/")
    def homepage(request):
        return PlainTextResponse("x" * 4000, status_code=200)

    client = client_factory(app)
    response = client.get("/", headers={"accept-encoding": "gzip"})
    assert response.status_code == 200
    assert response.text == "x" * 4000
    assert response.headers["content-encoding"] == "gzip"
    assert int(response.headers["content-length"]) < 4000


def test_gzip_not_in_accept_encoding(client_factory):
    app = Yaa(plugins={"http": {"middlewares": {"gzip": {}}}})

    @app.route("/")
    def homepage(request):
        return PlainTextResponse("x" * 4000, status_code=200)

    client = client_factory(app)
    response = client.get("/", headers={"accept-encoding": "identity"})
    assert response.status_code == 200
    assert response.text == "x" * 4000
    assert "Content-Encoding" not in response.headers
    assert int(response.headers["Content-Length"]) == 4000


def test_gzip_ignored_for_small_responses(client_factory):
    app = Yaa(plugins={"http": {"middlewares": {"gzip": {}}}})

    @app.route("/")
    def homepage(request):
        return PlainTextResponse("OK", status_code=200)

    client = client_factory(app)
    response = client.get("/", headers={"accept-encoding": "gzip"})
    assert response.status_code == 200
    assert response.text == "OK"
    assert "Content-Encoding" not in response.headers
    assert int(response.headers["Content-Length"]) == 2


def test_gzip_streaming_response(client_factory):
    app = Yaa(plugins={"http": {"middlewares": {"gzip": {}}}})

    @app.route("/")
    def homepage(request):
        async def generator(bytes, count):
            for index in range(count):
                yield bytes

        streaming = generator(bytes=b"x" * 400, count=10)
        return StreamingResponse(streaming, status_code=200)

    client = client_factory(app)
    response = client.get("/", headers={"accept-encoding": "gzip"})
    assert response.status_code == 200
    assert response.text == "x" * 4000
    assert response.headers["Content-Encoding"] == "gzip"
    assert "Content-Length" not in response.headers


def test_gzip_ignored_for_responses_with_encoding_set(client_factory):
    def homepage(request):
        async def generator(bytes, count):
            for index in range(count):
                yield bytes

        streaming = generator(bytes=b"x" * 400, count=10)
        return StreamingResponse(
            streaming, status_code=200, headers={"Content-Encoding": "br"}
        )

    from yaa.routing import Route

    app = Yaa(
        routes=[Route("/", endpoint=homepage)],
        plugins={"http": {"middlewares": {"gzip": {}}}},
    )
    client = client_factory(app)
    response = client.get("/", headers={"accept-encoding": "gzip, br"})
    assert response.status_code == 200
    assert response.text == "x" * 4000
    assert response.headers["Content-Encoding"] == "br"
    assert "Content-Length" not in response.headers
