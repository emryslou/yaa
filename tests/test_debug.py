import pytest

from yast import TestClient
from yast.debug import DebugMiddleware

def test_debug_text():
    def app(scope):
        async def asgi(recevie, send):
            raise RuntimeError('Something went wrong')
        
        return asgi
    
    client = TestClient(DebugMiddleware(app))
    res = client.get('/')    
    assert res.status_code == 500
    assert '<html>' not in res.text
    assert 'Something went wrong' in res.text


def test_debug_text():
    def app(scope):
        async def asgi(recevie, send):
            raise RuntimeError('Something went wrong')
        
        return asgi
    
    client = TestClient(DebugMiddleware(app))
    res = client.get('/', headers={'accept': 'text/html, */*'})    
    assert res.status_code == 500
    assert res.headers['content-type'].startswith('text/html')
    assert '<html>' in res.text
    assert 'Something went wrong' in res.text
