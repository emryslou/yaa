import pytest

from yast import TestClient
from yast.plugins.lifespan.middlewares import EventType, LifespanMiddleware


class App:
    raise_on = {}

    def __init__(self, scope):
        pass

    async def __call__(self, receive, send):
        for event_type in list(EventType):
            msg = await receive()
            if self.raise_on.get(str(event_type), False):
                raise RuntimeError()
            assert msg["type"] == event_type.lifespan
            await send({"type": event_type.complete})


class RaiseOnStartup(App):
    raise_on = {"startup": True}


class RaiseOnShutdown(App):
    raise_on = {"shutdown": True}


def test_sync_handler():
    startup_complete = False
    shutdown_complete = False

    handler = LifespanMiddleware(App)

    @handler.on_event("startup")
    def _su():
        nonlocal startup_complete
        startup_complete = True

    @handler.on_event("shutdown")
    def _sd():
        nonlocal shutdown_complete
        shutdown_complete = True

    assert not startup_complete
    assert not shutdown_complete
    with TestClient(handler):
        assert startup_complete
        assert not shutdown_complete

    assert startup_complete
    assert shutdown_complete


def test_async_handler():
    startup_complete = False
    shutdown_complete = False

    handler = LifespanMiddleware(App)

    @handler.on_event("startup")
    async def _su():
        nonlocal startup_complete
        startup_complete = True

    @handler.on_event("shutdown")
    async def _sd():
        nonlocal shutdown_complete
        shutdown_complete = True

    assert not startup_complete
    assert not shutdown_complete
    with TestClient(handler):
        assert startup_complete
        assert not shutdown_complete

    assert startup_complete
    assert shutdown_complete


def test_raise_on():
    handler = LifespanMiddleware(RaiseOnStartup)

    with pytest.raises(RuntimeError):
        with TestClient(handler):
            pass  # pragma: nocover

    handler = LifespanMiddleware(RaiseOnShutdown)

    with pytest.raises(RuntimeError):
        with TestClient(handler):
            pass  # pragma: nocover


def test_app():
    from yast import Yast

    app = Yast()

    startup_complete = False
    shutdown_complete = False

    @app.on_event("startup")
    async def _su():
        nonlocal startup_complete
        startup_complete = True

    @app.on_event("shutdown")
    async def _sd():
        nonlocal shutdown_complete
        shutdown_complete = True

    assert not startup_complete
    assert not shutdown_complete
    with TestClient(app):
        assert startup_complete
        assert not shutdown_complete

    assert startup_complete
    assert shutdown_complete
