from yast.applications import Yast
from yast.plugins.lifespan.routing import Lifespan
from yast.routing import Route, Router
from yast.testclient import TestClient


def test_route_lifespan():
    from yast.responses import PlainTextResponse

    startup_complete = False
    shutdown_complete = False

    def hello(req):
        return PlainTextResponse("hello")

    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    def run_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    app = Router(
        routes=[
            Lifespan(startup=[run_startup], shutdown=[run_shutdown]),
            Route("/", hello),
        ]
    )

    assert not startup_complete
    assert not shutdown_complete
    with TestClient(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_app():
    startup_complete = False
    shutdown_complete = False

    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    def run_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    app = Yast(
        plugins={
            "lifespan": {
                "event_handlers": {"startup": [run_startup], "shutdown": [run_shutdown]}
            },
        }
    )

    assert not startup_complete
    assert not shutdown_complete
    with TestClient(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_app_on_event_shutdown():
    startup_complete = False
    shutdown_complete = False

    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    app = Yast(
        plugins={
            "lifespan": {
                "event_handlers": {
                    "startup": [run_startup],
                }
            },
        }
    )

    @app.on_event("shutdown")
    def run_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    assert not startup_complete
    assert not shutdown_complete
    with TestClient(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_app_on_event_startup():
    startup_complete = False
    shutdown_complete = False

    def run_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    app = Yast(
        plugins={
            "lifespan": {"event_handlers": {"shutdown": [run_shutdown]}},
        }
    )

    @app.on_event("startup")
    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    assert not startup_complete
    assert not shutdown_complete
    with TestClient(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_app_add_event_handler():
    startup_complete = False
    shutdown_complete = False

    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    def run_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    app = Yast(
        plugins={
            "lifespan": {},
        }
    )

    app.add_event_handler("startup", run_startup)
    app.add_event_handler("shutdown", run_shutdown)

    assert not startup_complete
    assert not shutdown_complete
    with TestClient(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_startup_runtime_error():
    import pytest

    startup_failed = False

    def run_startup():
        raise RuntimeError()

    router = Router(routes=[Lifespan(startup=[run_startup])])

    async def app(scope, receive, send):
        async def _send(message):
            nonlocal startup_failed
            if message["type"] == "lifespan.startup.failed":
                startup_failed = True

            return await send(message)

        await router(scope, receive, _send)

    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass  # pragma: nocover

    assert startup_failed


def test_app_params():
    startup_complete = False
    shutdown_complete = False

    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    def run_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    app = Yast(
        on_shutdown=[run_shutdown],
        on_startup=[run_startup],
    )

    assert not startup_complete
    assert not shutdown_complete
    with TestClient(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete