import os

from yast.app import Yast
from yast.requests import Request
from yast.responses import PlainTextResponse, JSONResponse
from yast.routing import Router
from yast.staticfiles import StaticFiles
from yast.testclient import TestClient

app = Yast()
client = TestClient(app)

@app.exception_handle(Exception)
async def error_500(req: Request, exc):
    return JSONResponse({'detail': 'oo....ooo'}, status_code=500)

def _add_router():
    @app.route('/')
    def func_homepage(request):
        return PlainTextResponse('Hello, func_homepage')

    @app.route('/async')
    async def afun(request):
        return PlainTextResponse('Hello, afun')

    @app.route('/kwargs/{arg0}')
    def func_kwargs(request, **kwargs):
        return JSONResponse({'func': 'func_kwargs', 'kwargs': kwargs})

    @app.route('/kwargs1/{arg1}')
    def func_kwargs(request, arg1):
        return JSONResponse({'func': 'func_kwargs', 'arg1': arg1})

def test_func_route():
    
    _add_router()

    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'Hello, func_homepage'

    res = client.get('/async')
    assert res.status_code == 200
    assert res.text == 'Hello, afun'

    res = client.get('/kwargs/aaa')
    assert res.status_code == 200
    assert res.json() == {'func': 'func_kwargs', 'kwargs': {'arg0': 'aaa'}}

    res = client.get('/kwargs1/aaa')
    assert res.status_code == 200
    assert res.json() == {'func': 'func_kwargs', 'arg1': 'aaa'}


def test_ws_route():
    @app.ws_route('/ws')
    async def ws_endpoint(session):
        await session.accept()
        await session.send_text('Hello, Ws')
        await session.close()
    
    with client.wsconnect('/ws') as s:
        text = s.recevie_text()
        assert text == 'Hello, Ws'

def test_400():
    _add_router()
    res = client.get('/404')
    assert res.status_code == 404

def test_app_mount(tmpdir):
    path = os.path.join(tmpdir, 'example.txt')

    with open(path, 'w') as f:
        f.write('<file content>')
    
    app.mount('/static', StaticFiles(directory=tmpdir))

    res = client.get('/static/example.txt')
    assert res.status_code == 200
    assert res.text == '<file content>'

    res = client.get('/static/nop.txt')
    assert res.status_code == 404


def test_app_error():
    client = TestClient(app, raise_server_exceptions=False)
    @app.route('/err_500')
    def _tmp(request: Request):
        raise Exception()

    res = client.get('/err_500')
    assert res.status_code == 500
    assert res.json() == {'detail': 'oo....ooo'}

    res = client.post('/err_500')
    assert res.status_code == 405
    assert res.text ==  'Method Not Allowed'