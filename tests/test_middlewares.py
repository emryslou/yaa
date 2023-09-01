import pytest

from yast.applications import Yast
from yast.responses import PlainTextResponse
from yast.testclient import TestClient


def test_middleware_trustedhost():
    from yast.middlewares import TrustedHostMiddleware

    app = Yast()

    @app.route('/')
    async def home(_):
        return PlainTextResponse('OK')
    
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['aa.com', 'bb.com'])

    client = TestClient(app, base_url='http://aa.com')
    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'OK'

    client = TestClient(app, base_url='http://bb.com')
    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'OK'

    client = TestClient(app, base_url='http://xx.com')
    res = client.get('/')
    assert res.status_code == 400
    assert res.text == 'Invalid host header'


def test_middleware_httpredirect():
    from yast.middlewares import HttpsRedirectMiddleware

    app = Yast()

    @app.route('/')
    async def home(_):
        return PlainTextResponse('OK')
    
    app.add_middleware(HttpsRedirectMiddleware)

    client = TestClient(app, base_url='https://testserver')
    res = client.get('/?type=https')
    assert res.status_code == 200

    client = TestClient(app)
    res = client.get('/?type=http', allow_redirects=False)
    assert res.status_code == 301
    assert res.headers['location'] == 'https://testserver/?type=http'


def test_middleware_cors_allow_all():
    from yast.middlewares import CORSMiddleware

    app = Yast()

    @app.route('/')
    async def home(_):
        return PlainTextResponse('HOME')
    

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_headers = ['*'],
        allow_methods = ['*'],
        expose_headers = ['X-Status'],
        allow_credentials=True,
    )

    client = TestClient(app)
    headers = {
        'Origin': 'https://ex.org',
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'X-Example',
    }

    res = client.options('/', headers=headers)
    assert res.status_code == 200
    assert res.text == 'OK'
    assert res.headers['access-control-allow-origin'] == '*'
    assert 'access-control-allow-headers' in res.headers
    assert res.headers['access-control-allow-headers'] == 'X-Example'

    headers = {
        'Origin': 'https://ex.org',
    }
    res = client.get('/', headers=headers)
    assert res.status_code == 200
    assert res.text == 'HOME'
    assert 'access-control-allow-headers' not in res.headers


def test_middleware_cors_specific_origin():
    from yast.middlewares import CORSMiddleware

    app = Yast()

    @app.route('/')
    async def home(_):
        return PlainTextResponse('HOME')
    

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['https://ex.org'],
        allow_headers = ['X-Example'],
    )

    client = TestClient(app)
    headers = {
        'Origin': 'https://ex.org',
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'X-Example',
    }
    res = client.options('/', headers=headers)
    assert res.status_code == 200
    assert res.text == 'OK'
    assert 'access-control-allow-origin' in res.headers
    assert res.headers['access-control-allow-origin'] == 'https://ex.org'
    assert 'access-control-allow-headers' in res.headers
    assert res.headers['access-control-allow-headers'] == 'X-Example'

    headers = {'Origin': 'https://ex.org'}
    res = client.get('/', headers=headers)
    assert res.status_code == 200
    assert res.text == 'HOME'
    assert 'access-control-allow-origin' in res.headers
    assert res.headers['access-control-allow-origin'] == 'https://ex.org'

    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'HOME'
    assert 'access-control-allow-origin' not in res.headers


def test_middleware_cors_disallowed_preflight():
    from yast.middlewares import CORSMiddleware

    app = Yast()

    @app.route('/')
    async def home(_):
        return PlainTextResponse('HOME')
    

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['https://ex.org'],
        allow_headers = ['X-Example'],
    )

    client = TestClient(app)

    headers ={
        'Origin': 'https://unknown.org',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'X-Foo',
    }

    res = client.options('/', headers=headers)
    assert res.status_code == 400
    assert res.text == 'Disallowed CORS origin,method,headers'

def test_middleware_cors_allow_origin_regex():
    from yast.middlewares import CORSMiddleware
    app = Yast()
    app.add_middleware(
        CORSMiddleware, allow_headers=["X-Example"], allow_origin_regex="https://*"
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
        "Access-Control-Request-Headers": "X-Example",
    }
    response = client.options("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "OK"
    assert response.headers["access-control-allow-origin"] == "https://another.com"
    assert response.headers["access-control-allow-headers"] == "X-Example"
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
