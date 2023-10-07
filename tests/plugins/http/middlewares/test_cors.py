from yaa import Yaa, TestClient
from yaa.responses import PlainTextResponse


def test_cors_allow_all():
    app = Yaa(
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
    assert res.headers["access-control-allow-origin"] == "https://ex.org"
    assert "access-control-allow-headers" in res.headers
    assert res.headers["access-control-allow-headers"] == "X-Example"
    assert res.headers["access-control-allow-credentials"] == "true"
    assert res.headers["vary"] == "Origin"

    headers = {
        "Origin": "https://ex.org",
    }
    res = client.get("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "HOME"
    assert res.headers["access-control-allow-origin"] == "*"
    assert res.headers["access-control-expose-headers"] == "X-Status"
    assert res.headers["access-control-allow-credentials"] == "true"

    # Test standard credentialed response
    headers = {"Origin": "https://example.org", "Cookie": "star_cookie=sugar"}
    res = client.get("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "HOME"
    assert res.headers["access-control-allow-origin"] == "https://example.org"
    assert res.headers["access-control-expose-headers"] == "X-Status"
    assert res.headers["access-control-allow-credentials"] == "true"

    # Test non-CORS response
    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "HOME"
    assert "access-control-allow-origin" not in res.headers


def test_cors_allow_all_except_credentials():
    app = Yaa(
        plugins={
            "http": {
                "middlewares": {
                    "cors": dict(
                        allow_origins=["*"],
                        allow_headers=["*"],
                        allow_methods=["*"],
                        expose_headers=["X-Status"],
                    )
                }
            }
        }
    )

    @app.route("/")
    def homepage(request):
        return PlainTextResponse("Homepage", status_code=200)

    client = TestClient(app)
    # Test pre-flight response
    headers = {
        "Origin": "https://example.org",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-Example",
    }
    response = client.options("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "OK"
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-headers"] == "X-Example"
    assert "access-control-allow-credentials" not in response.headers
    assert "vary" not in response.headers
    # Test standard response
    headers = {"Origin": "https://example.org"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Homepage"
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-expose-headers"] == "X-Status"
    assert "access-control-allow-credentials" not in response.headers
    # Test non-CORS response
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "Homepage"
    assert "access-control-allow-origin" not in response.headers


def test_cors_specific_origin():
    app = Yaa(
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

    allow_headers = res.headers["access-control-allow-headers"].split(", ")
    for tcase in "X-Example, Content-Type".split(", "):
        assert tcase in allow_headers

    assert "access-control-allow-credentials" not in res.headers

    headers = {"Origin": "https://ex.org"}
    res = client.get("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "HOME"
    assert "access-control-allow-origin" in res.headers
    assert res.headers["access-control-allow-origin"] == "https://ex.org"
    assert "access-control-allow-credentials" not in res.headers

    res = client.get("/")
    assert res.status_code == 200
    assert res.text == "HOME"
    assert "access-control-allow-origin" not in res.headers
    assert "access-control-allow-credentials" not in res.headers


def test_cors_disallowed_preflight():
    app = Yaa(
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

    headers = {
        "Origin": "https://ex.org",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-Nope-1, X-Nope-2",
    }
    response = client.options("/", headers=headers)
    assert response.text == "Disallowed CORS headers"


def test_cors_allow_origin_regex():
    app = Yaa(
        plugins={
            "http": {
                "middlewares": {
                    "cors": dict(
                        allow_headers=["X-Example", "Content-Type"],
                        allow_origin_regex="https://.*",
                        allow_credentials=True,
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
    assert response.headers["access-control-allow-credentials"] == "true"

    # Test standard credentialed response
    headers = {"Origin": "https://example.org", "Cookie": "star_cookie=sugar"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Homepage"
    assert response.headers["access-control-allow-origin"] == "https://example.org"
    assert response.headers["access-control-allow-credentials"] == "true"

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
    assert "access-control-allow-headers" in response.headers
    allow_headers = response.headers["access-control-allow-headers"].split(", ")
    for tcase in "X-Example, Content-Type".split(", "):
        assert tcase in allow_headers
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
    app = Yaa(plugins={"http": {"middlewares": {"cors": dict(allow_origins=["*"])}}})

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
    app = Yaa(
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


def test_cors_vary_header_is_not_set_for_non_credentialed_request():
    app = Yaa(plugins={"http": {"middlewares": {"cors": dict(allow_origins=["*"])}}})

    @app.route("/")
    def homepage(_):
        return PlainTextResponse("HomePage", headers={"Vary": "Accept-Encoding"})

    client = TestClient(app)
    headers = {"Origin": "https://example.org"}
    res = client.get("/", headers=headers)
    assert res.status_code == 200
    assert res.text == "HomePage"
    assert res.headers["vary"] == "Accept-Encoding"


def test_cors_vary_header_is_properly_set_for_credentialed_request():
    app = Yaa(plugins={"http": {"middlewares": {"cors": dict(allow_origins=["*"])}}})

    @app.route("/")
    def homepage(request):
        return PlainTextResponse(
            "Homepage", status_code=200, headers={"Vary": "Accept-Encoding"}
        )

    client = TestClient(app)
    response = client.get(
        "/", headers={"Cookie": "foo=bar", "Origin": "https://someplace.org"}
    )
    assert response.status_code == 200
    assert response.headers["vary"] == "Accept-Encoding, Origin"


def test_cors_vary_header_is_properly_set_for_credentialed_request():
    app = Yaa(plugins={"http": {"middlewares": {"cors": dict(allow_origins=["*"])}}})

    @app.route("/")
    def homepage(request):
        return PlainTextResponse(
            "Homepage", status_code=200, headers={"Vary": "Accept-Encoding"}
        )

    client = TestClient(app)
    response = client.get(
        "/", headers={"Cookie": "foo=bar", "Origin": "https://someplace.org"}
    )
    assert response.status_code == 200
    assert response.headers["vary"] == "Accept-Encoding, Origin"


def test_cors_vary_header_is_properly_set_when_allow_origins_is_not_wildcard():
    app = Yaa(
        plugins={
            "http": {
                "middlewares": {"cors": dict(allow_origins=["https://example.org"])}
            }
        }
    )

    @app.route("/")
    def homepage(request):
        return PlainTextResponse(
            "Homepage", status_code=200, headers={"Vary": "Accept-Encoding"}
        )

    client = TestClient(app)
    response = client.get("/", headers={"Origin": "https://example.org"})
    assert response.status_code == 200
    assert response.headers["vary"] == "Accept-Encoding, Origin"


def test_cors_allow_origin_regex_fullmatch():
    app = Yaa(
        plugins={
            "http": {
                "middlewares": {
                    "cors": dict(
                        allow_headers=["X-Example", "Content-Type"],
                        allow_origin_regex="https://.*\.example.org",
                    ),
                }
            }
        }
    )

    @app.route("/")
    def homepage(request):
        return PlainTextResponse("Homepage", status_code=200)

    client = TestClient(app)
    # Test standard response
    headers = {"Origin": "https://subdomain.example.org"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Homepage"
    assert (
        response.headers["access-control-allow-origin"]
        == "https://subdomain.example.org"
    )
    # Test diallowed standard response
    headers = {"Origin": "https://subdomain.example.org.hacker.com"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Homepage"
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_allow_all_methods():
    app = Yaa(
        plugins={
            "http": {
                "middlewares": {
                    "cors": dict(
                        allow_origins=["*"],
                        allow_methods=["*"],
                    )
                }
            }
        }
    )

    @app.route("/")
    def homepage(request):
        pass  # pragma: no cover

    client = TestClient(app)
    headers = {
        "Origin": "https://example.org",
        "Access-Control-Request-Method": "POST",
    }
    for method in ("DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"):
        response = client.options("/", headers=headers)
        assert response.status_code == 200
        assert method in response.headers["access-control-allow-methods"]


def test_cors_allow_all_methods():
    app = Yaa(
        plugins={
            "http": {
                "middlewares": {
                    "cors": dict(
                        allow_origins=["*"],
                        allow_methods=["*"],
                    )
                }
            }
        }
    )

    @app.route(
        "/", methods=("delete", "get", "head", "options", "patch", "post", "put")
    )
    def homepage(request):
        return PlainTextResponse("Homepage", status_code=200)

    client = TestClient(app)
    headers = {"Origin": "https://example.org"}
    for method in ("delete", "get", "head", "options", "patch", "post", "put"):
        response = getattr(client, method)("/", headers=headers, json={})
        assert response.status_code == 200
