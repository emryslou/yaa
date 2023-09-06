import pytest
import typing

from yast import Yast, TestClient
from yast.middlewares import BaseHttpMiddleware
from yast.requests import Request
from yast.responses import PlainTextResponse
from yast.types import ASGIInstance

class VenderMiddleware(BaseHttpMiddleware):
    async def dispath(
            self, req: Request, call_next: typing.Callable
        ) -> ASGIInstance:
        res = await call_next(req)
        res.headers['Vendor-Header'] = 'Vendor'
        return res

app = Yast()
app.add_middleware(VenderMiddleware)

@app.route('/')
def _(_):
    return PlainTextResponse('index')

@app.route('/exc')
def exc(_):
    raise Exception()

@app.route('/rterr')
def rterr(_):
    raise RuntimeError()

@app.ws_route('/ws')
async def ws_ep(s):
    await s.accept()
    await s.send_text('ws_ep')
    await s.close()


@app.route('/no_res')
class NoResApp:
    def __init__(self, scope):
        pass

    async def __call__(self, r, s):
        pass

def test_vendor():
    client = TestClient(app)
    res = client.get('/')
    assert 'Vendor-Header' in res.headers
    assert res.headers['Vendor-Header'] == 'Vendor'

    with pytest.raises(Exception):
        response = client.get("/exc")
    with pytest.raises(RuntimeError):
        response = client.get("/rterr")

    with client.wsconnect("/ws") as session:
        text = session.receive_text()
        assert text == "ws_ep"
    
    with pytest.raises(RuntimeError):
        client.get('/no_res')