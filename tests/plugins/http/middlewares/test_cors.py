from yast import Yast, TestClient
from yast.responses import PlainTextResponse


def test_cors_allow_all():
    app = Yast(
        plugins={
            "http": {
                "middlewares": {
                    "cors": dict(
                        allow_origins=["*"],
                        allow_headers=["*"],
                        allow_methods=["*"],
                        expose_headers=["X-Status"],
                        allow_credentials=True,
                    )
                }
            }
        }
    )

    @app.route("/")
    async def home(_):
        return PlainTextResponse("HOME")

    client = TestClient(app)
    headers = {
        "Origin": "https://ex.org",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-Example",
    }

    res = client.options("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "OK"
    assert res.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-headers" in res.headers
    assert res.headers["access-control-allow-headers"] == "X-Example"

    headers = {
        "Origin": "https://ex.org",
    }
    res = client.get("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "HOME"
    assert "access-control-allow-headers" not in res.headers


def test_cors_specific_origin():
    app = Yast(
        plugins={
            "http": {
                "middlewares": {
                    "cors": dict(
                        allow_origins=["https://ex.org"],
                        allow_headers=["X-Example", "Content-Type"],
                    )
                }
            }
        }
    )

    @app.route("/")
    async def home(_):
        return PlainTextResponse("HOME")

    client = TestClient(app)
    headers = {
        "Origin": "https://ex.org",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-Example, Content-Type",
    }
    res = client.options("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "OK"
    assert "access-control-allow-origin" in res.headers
    assert res.headers["access-control-allow-origin"] == "https://ex.org"
    assert "access-control-allow-headers" in res.headers
    assert res.headers["access-control-allow-headers"] == "X-Example, Content-Type"

    headers = {"Origin": "https://ex.org"}
    res = client.get("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "HOME"
    assert "access-control-allow-origin" in res.headers
    assert res.headers["access-control-allow-origin"] == "https://ex.org"

    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "HOME"
    assert "access-control-allow-origin" not in res.headers


def test_cors_disallowed_preflight():
    app = Yast(
        plugins={
            "http": {
                "middlewares": {
                    "cors": dict(
                        allow_origins=["https://ex.org"],
                        allow_headers=["X-Example"],
                    )
                }
            }
        }
    )

    @app.route("/")
    async def home(_):
        return PlainTextResponse("HOME")  # pragma: nocover

    client = TestClient(app)

    headers = {
        "Origin": "https://unknown.org",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-Foo",
    }

    res = client.options("/", headers=headers)
    assert res.status_code == 400
    assert res.text == "Disallowed CORS origin,method,headers"


def test_cors_allow_origin_regex():
    app = Yast(
        plugins={
            "http": {
                "middlewares": {
                    "cors": dict(
                        allow_headers=["X-Example", "Content-Type"],
                        allow_origin_regex="https://*",
                    )
                }
            }
        }
    )

    @app.route("/")
    def homepage(request):
        return PlainTextResponse("Homepage", status_code=200)

    client = TestClient(app)
    # Test standard response
    headers = {"Origin": "https://example.org"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Homepage"
    assert response.headers["access-control-allow-origin"] == "https://example.org"
    # Test diallowed standard response
    # Note that enforcement is a browser concern. The disallowed-ness is reflected
    # in the lack of an "access-control-allow-origin" header in the response.
    headers = {"Origin": "http://example.org"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Homepage"
    assert "access-control-allow-origin" not in response.headers
    # Test pre-flight response
    headers = {
        "Origin": "https://another.com",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-Example, Content-Type",
    }
    response = client.options("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "OK"
    assert response.headers["access-control-allow-origin"] == "https://another.com"
    assert response.headers["access-control-allow-headers"] == "X-Example, Content-Type"
    # Test disallowed pre-flight response
    headers = {
        "Origin": "http://another.com",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-Example",
    }
    response = client.options("/", headers=headers)
    assert response.status_code == 400
    assert response.text == "Disallowed CORS origin"
    assert "access-control-allow-origin" not in response.headers


def test_cors_credentialed_requests_return_specific_origin():
    app = Yast(plugins={"http": {"middlewares": {"cors": dict(allow_origins=["*"])}}})

    @app.route("/")
    def homepage(_):
        return PlainTextResponse("HomePage")

    client = TestClient(app)
    headers = {"Origin": "https://example.org", "Cookie": "start_cookie=sugar"}
    res = client.get("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "HomePage"
    assert res.headers["access-control-allow-origin"] == "https://example.org"


def test_cors_vary_header_defaults_to_orgin():
    app = Yast(
        plugins={
            "http": {
                "middlewares": {"cors": dict(allow_origins=["https://example.org"])}
            }
        }
    )

    @app.route("/")
    def homepage(_):
        return PlainTextResponse("HomePage")

    client = TestClient(app)
    headers = {"Origin": "https://example.org"}
    res = client.get("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "HomePage"
    assert res.headers["vary"] == "Origin"


def test_cors_vary_header_is_properly_set():
    app = Yast(
        plugins={
            "http": {
                "middlewares": {"cors": dict(allow_origins=["https://example.org"])}
            }
        }
    )

    @app.route("/")
    def homepage(_):
        return PlainTextResponse("HomePage", headers={"Vary": "Accept-Encoding"})

    client = TestClient(app)
    headers = {"Origin": "https://example.org"}
    res = client.get("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "HomePage"
    assert res.headers["vary"] == "Accept-Encoding, Origin"
