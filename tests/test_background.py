import asyncio
import pytest

from yast import TestClient
from yast.background import BackgroundTask
from yast.requests import Request
from yast.responses import Response


@pytest.mark.timeout(3)
def test_async_task():
    TASK_DONE = False

    async def async_task():
        nonlocal TASK_DONE
        count = 0
        for num in range(2):
            count += 1
            await asyncio.sleep(1)
        TASK_DONE = True
        return count

    task = BackgroundTask(async_task)

    def app(scope):
        async def asgi(receive, send):
            res = Response("task initiated", media_type="text/plain", background=task)
            await res(receive, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.text == "task initiated"
    assert TASK_DONE


@pytest.mark.timeout(3)
def test_sync_task():
    TASK_DONE = False

    def sync_task():
        nonlocal TASK_DONE
        count = 0
        for num in range(500):
            count += 1
        TASK_DONE = True
        return count

    task = BackgroundTask(sync_task)

    def app(scope):
        async def asgi(receive, send):
            res = Response("task initiated", media_type="text/plain", background=task)
            await res(receive, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.text == "task initiated"
    assert TASK_DONE
