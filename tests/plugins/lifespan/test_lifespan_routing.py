import contextlib, pytest

from yaa.applications import Yaa
from yaa.plugins.lifespan.routing import Lifespan
from yaa.responses import PlainTextResponse
from yaa.routing import Route, Router, Mount


def test_route_lifespan_handlers(client_factory):
    from yaa.responses import PlainTextResponse

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
    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_route_sync_lifespan(client_factory):
    from yaa.responses import PlainTextResponse

    startup_complete = False
    shutdown_complete = False

    def hello(req):
        return PlainTextResponse("hello")

    def lifespan(app):
        nonlocal startup_complete, shutdown_complete
        startup_complete = True
        yield
        shutdown_complete = True

    app = Router(
        routes=[
            Lifespan(context=lifespan),
            Route("/", hello),
        ]
    )

    assert not startup_complete
    assert not shutdown_complete
    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_route_async_lifespan(client_factory):
    from yaa.responses import PlainTextResponse

    startup_complete = False
    shutdown_complete = False

    def hello(req):
        return PlainTextResponse("hello")

    async def lifespan(app):
        nonlocal startup_complete, shutdown_complete
        startup_complete = True
        yield
        shutdown_complete = True

    app = Router(
        routes=[
            Lifespan(context=lifespan),
            Route("/", hello),
        ]
    )

    assert not startup_complete
    assert not shutdown_complete
    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_app(client_factory):
    startup_complete = False
    shutdown_complete = False

    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    def run_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    app = Yaa(
        plugins={
            "lifespan": {
                "event_handlers": {"startup": [run_startup], "shutdown": [run_shutdown]}
            },
        }
    )

    assert not startup_complete
    assert not shutdown_complete
    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_app_plugin_lifespan(client_factory):
    from yaa.responses import PlainTextResponse

    startup_complete = False
    shutdown_complete = False

    def hello(req):
        return PlainTextResponse("hello")  # pragma: no cover

    async def lifespan(app):
        nonlocal startup_complete, shutdown_complete
        startup_complete = True
        yield
        shutdown_complete = True

    app = Yaa(
        plugins={
            "lifespan": {"context": lifespan},
        }
    )

    assert not startup_complete
    assert not shutdown_complete
    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_app_params_lifespan(client_factory):
    from yaa.responses import PlainTextResponse

    startup_complete = False
    shutdown_complete = False

    def hello(req):
        return PlainTextResponse("hello")  # pragma: no cover

    async def lifespan(app):
        nonlocal startup_complete, shutdown_complete
        startup_complete = True
        yield
        shutdown_complete = True

    app = Yaa(lifespan=lifespan)

    assert not startup_complete
    assert not shutdown_complete
    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_app_on_event_shutdown(client_factory):
    startup_complete = False
    shutdown_complete = False

    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    app = Yaa(
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
    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_app_on_event_startup(client_factory):
    startup_complete = False
    shutdown_complete = False

    def run_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    app = Yaa(
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
    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_app_add_event_handler(client_factory):
    startup_complete = False
    shutdown_complete = False

    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    def run_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    app = Yaa(
        plugins={
            "lifespan": {},
        }
    )

    app.add_event_handler("startup", run_startup)
    app.add_event_handler("shutdown", run_shutdown)

    assert not startup_complete
    assert not shutdown_complete
    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


def test_startup_runtime_error(client_factory):
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
        with client_factory(app):
            pass  # pragma: nocover

    assert startup_failed


def test_app_params(client_factory):
    startup_complete = False
    shutdown_complete = False

    def run_startup():
        nonlocal startup_complete
        startup_complete = True

    def run_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    app = Yaa(
        on_shutdown=[run_shutdown],
        on_startup=[run_startup],
    )

    assert not startup_complete
    assert not shutdown_complete
    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
    assert startup_complete
    assert shutdown_complete


deprecated_lifespan = pytest.mark.filterwarnings(
    r"ignore"
    r":(async )?generator function lifespans are deprecated, use an "
    r"@contextlib\.asynccontextmanager function instead"
    r":DeprecationWarning"
    r":starlette.routing"
)


@deprecated_lifespan
def test_async_gen_lifespan(client_factory):
    startup_complete = False
    cleanup_complete = False

    async def lifespan(app):
        nonlocal startup_complete, cleanup_complete
        startup_complete = True
        yield
        cleanup_complete = True

    app = Yaa(lifespan=lifespan)
    assert not startup_complete
    assert not cleanup_complete
    with client_factory(app):
        assert startup_complete
        assert not cleanup_complete
    assert startup_complete
    assert cleanup_complete


@deprecated_lifespan
def test_sync_gen_lifespan(client_factory):
    startup_complete = False
    cleanup_complete = False

    def lifespan(app):
        nonlocal startup_complete, cleanup_complete
        startup_complete = True
        yield
        cleanup_complete = True

    app = Yaa(lifespan=lifespan)
    assert not startup_complete
    assert not cleanup_complete
    with client_factory(app):
        assert startup_complete
        assert not cleanup_complete
    assert startup_complete
    assert cleanup_complete


def test_lifespan_with_state(client_factory):
    startup_complete = False
    shutdown_complete = False

    async def hello_world(request):
        # modifications to the state should not leak across requests
        assert request.state.count == 0
        # modify the state, this should not leak to the lifespan or other requests
        request.state.count += 1
        # since state.list is a mutable object this modification _will_ leak across
        # requests and to the lifespan
        request.state.list.append(1)
        return PlainTextResponse("hello, world")

    async def run_startup(state):
        nonlocal startup_complete
        startup_complete = True
        state["count"] = 0
        state["list"] = []

    async def run_shutdown(state):
        nonlocal shutdown_complete
        shutdown_complete = True
        # modifications made to the state from a request do not leak to the lifespan
        assert state["count"] == 0
        # unless of course the request mutates a mutable object that is referenced
        # via state
        assert state["list"] == [1, 1]

    from yaa.plugins.lifespan.routing import Lifespan

    app = Yaa(
        on_startup=[run_startup],
        on_shutdown=[run_shutdown],
        routes=[Route("/", hello_world)],
    )

    assert not startup_complete
    assert not shutdown_complete

    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
        # Calling it a second time to ensure that the state is preserved.
        client.get("/")

    assert startup_complete
    assert shutdown_complete


def test_lifespan_state_unsupported(client_factory):
    @contextlib.asynccontextmanager
    async def lifespan(app, scope):
        yield None  # pragma: no cover

    app = Yaa(
        lifespan=lifespan,
        routes=[Mount("/", PlainTextResponse("hello, world"))],
    )

    async def no_state_wrapper(scope, receive, send):
        del scope["state"]
        await app(scope, receive, send)

    with pytest.raises(
        RuntimeError, match='The server does not support "state" in the lifespan scope'
    ):
        with client_factory(no_state_wrapper):
            raise AssertionError("Should not be called")  # pragma: no cover


def test_lifespan_async_cm(client_factory):
    startup_complete = False
    shutdown_complete = False

    async def hello_world(request):
        # modifications to the state should not leak across requests
        assert request.state.count == 0
        # modify the state, this should not leak to the lifespan or other requests
        request.state.count += 1
        # since state.list is a mutable object this modification _will_ leak across
        # requests and to the lifespan
        request.state.list.append(1)
        return PlainTextResponse("hello, world")

    @contextlib.asynccontextmanager
    async def lifespan(app, state):
        nonlocal startup_complete, shutdown_complete
        startup_complete = True
        state["count"] = 0
        state["list"] = []
        yield
        shutdown_complete = True
        # modifications made to the state from a request do not leak to the lifespan
        assert state["count"] == 0
        # unless of course the request mutates a mutable object that is referenced
        # via state
        assert state["list"] == [1, 1]

    app = Yaa(
        lifespan=lifespan,
        routes=[Route("/", hello_world)],
    )

    assert not startup_complete
    assert not shutdown_complete

    with client_factory(app) as client:
        assert startup_complete
        assert not shutdown_complete
        client.get("/")
        # Calling it a second time to ensure that the state is preserved.
        client.get("/")

    assert startup_complete
    assert shutdown_complete
