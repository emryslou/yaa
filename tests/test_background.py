import asyncio

import pytest

from yaa.background import BackgroundTask, BackgroundTasks
from yaa.requests import Request
from yaa.responses import Response


@pytest.mark.timeout(3)
def test_async_task(client_factory):
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

    async def app(scope, receive, send):
        res = Response("task initiated", media_type="text/plain", background=task)
        await res(scope, receive, send)

    client = client_factory(app)
    res = client.get("/")
    assert res.text == "task initiated"
    assert TASK_DONE


@pytest.mark.timeout(3)
def test_sync_task(client_factory):
    TASK_DONE = False

    def sync_task():
        nonlocal TASK_DONE
        count = 0
        for num in range(500):
            count += 1
        TASK_DONE = True
        return count

    task = BackgroundTask(sync_task)

    async def app(scope, receive, send):
        res = Response("task initiated", media_type="text/plain", background=task)
        await res(scope, receive, send)

    client = client_factory(app)
    res = client.get("/")
    assert res.text == "task initiated"
    assert TASK_DONE


def test_multiple_tasks(client_factory):
    TASK_COUNTER = 0

    def increment(amount):
        nonlocal TASK_COUNTER
        TASK_COUNTER += amount

    async def app(scope, receive, send):
        tasks = BackgroundTasks()
        tasks.add_task(increment, amount=1)
        tasks.add_task(increment, amount=2)
        tasks.add_task(increment, amount=3)
        response = Response(
            "tasks initiated", media_type="text/plain", background=tasks
        )
        await response(scope, receive, send)

    client = client_factory(app)
    response = client.get("/")
    assert response.text == "tasks initiated"
    assert TASK_COUNTER == 1 + 2 + 3
