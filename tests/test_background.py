import asyncio
import pytest

from yast import TestClient
from yast.background import BackgroundTask
from yast.requests import Request
from yast.responses import Response

@pytest.mark.timeout(3)
def test_async_task():
    async def async_task():
        count = 0
        for num in range(2):
            count += 1
            await asyncio.sleep(1)
        return count
    
    task = BackgroundTask(async_task)
    def app(scope):
        async def asgi(receive, send):
            res = Response('task initiated', media_type='text/plain', background=task)
            await res(receive, send)
        
        return asgi
    
    client = TestClient(app)
    res = client.get('/')
    assert res.text == 'task initiated'

@pytest.mark.timeout(3)
def test_sync_task():
    def sync_task():
        count = 0
        for num in range(500):
            count += 1
        return count
    
    task = BackgroundTask(sync_task)
    def app(scope):
        async def asgi(receive, send):
            res = Response('task initiated', media_type='text/plain', background=task)
            await res(receive, send)
        
        return asgi
    
    client = TestClient(app)
    res = client.get('/')
    assert res.text == 'task initiated'