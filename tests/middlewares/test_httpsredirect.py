from yast.applications import Yast
from yast.responses import PlainTextResponse
from yast.testclient import TestClient


def test_httpsredirect():
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
