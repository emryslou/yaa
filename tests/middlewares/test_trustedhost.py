import pytest

from yast.applications import Yast
from yast.responses import PlainTextResponse
from yast.testclient import TestClient


def test_trustedhost():
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