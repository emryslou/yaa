import pytest

from yast import TestClient
from yast.exceptions import ExceptionMiddleware, HttpException
from yast.responses import PlainTextResponse
from yast.routing import Router, Path


def raise_runtime_error(scope):
    async def asgi(receive, send):
        raise RuntimeError('W.c.')
    
    return asgi

def not_acceptable(scope):
    async def asgi(receive, send):
        raise HttpException(status_code=406)
    
    return asgi

def not_modified(scope):
    async def asgi(receive, send):
        raise HttpException(status_code=304)
    
    return asgi


def handled_exc_after_response(scope):
    async def asgi(receive, send):
        res = PlainTextResponse('OK', status_code=200)
        await res(receive, send)
        raise HttpException(status_code=406)
    
    return asgi

router = Router([
    Path('/runtime_error', app=raise_runtime_error),
    Path('/not_acceptable', app=not_acceptable),
    Path('/not_modified', app=not_modified),
    Path('/handled_exc_after_response', app=handled_exc_after_response)
])

app = ExceptionMiddleware(router)
client = TestClient(app)

def test_server_error():
    with pytest.raises(RuntimeError):
        res = client.get('/runtime_error')

    client500 = TestClient(app, raise_server_exceptions=False)

    res = client500.get('/runtime_error')
    assert res.status_code == 500
    assert res.text == 'Internal Server Error'

def test_debug_enabled():
    app = ExceptionMiddleware(router)
    app.debug = True

    client500 = TestClient(app, raise_server_exceptions=False)

    res = client500.get('/runtime_error')
    assert res.status_code == 500
    assert 'RuntimeError' in res.text

def test_not_acceptable():
    res = client.get('/not_acceptable')
    assert res.status_code == 406
    assert "Not Acceptable" == res.text

def test_not_modified():
    res = client.get('/not_modified')
    assert res.status_code == 304
    assert "" == res.text

def test_websockets_should_raise():
    with pytest.raises(RuntimeError):
        with client.wsconnect('/runtime_error') as _:
            pass
            
    # with pytest.raises(RuntimeError):
    #     client.wsconnect('/runtime_error')

def test_handled_exc_after_response():
    with pytest.raises(RuntimeError):
        client.get('/handled_exc_after_response')
    
    client200 = TestClient(app, raise_server_exceptions=False)
    res = client200.get('handled_exc_after_response')
    assert res.status_code == 200
    assert res.text == 'OK'

def test_force_500_res():
    def app(scope):
        raise RuntimeError()
    
    client_force_500 = TestClient(app, raise_server_exceptions=False)
    res = client_force_500.get('/')

    assert res.status_code == 500
    assert res.text == ''