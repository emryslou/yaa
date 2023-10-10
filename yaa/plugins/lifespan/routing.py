import asyncio
import contextlib
import functools
import inspect
import traceback
import typing
import warnings

from yaa.routing import BaseRoute, Match, Router
from yaa.types import Receive, Scope, Send

from .types import EventType

_T = typing.TypeVar("_T")


class _AsyncLiftContextManager(typing.AsyncContextManager[_T]):
    def __init__(self, cm: typing.ContextManager[_T]):
        self._cm = cm

    async def __aenter__(self) -> _T:
        return self._cm.__enter__()

    async def __aexit__(self, exc_type, exc_value, traceback):
        return self._cm.__exit__(exc_type, exc_value, traceback)


def _wrap_gen_lifespan_context(lifespan_context):
    cmgr = contextlib.contextmanager(lifespan_context)

    @functools.wraps(cmgr)
    def wrapper(app) -> _AsyncLiftContextManager:
        return _AsyncLiftContextManager(cmgr(app))

    return wrapper


class _DefaultLifespan:
    def __init__(self, router: "Router"):
        self._router = router

    async def __aenter__(self) -> _T:
        await self._router.handler(EventType.STARTUP)

    async def __aexit__(self, *exc_info: object):
        await self._router.handler(EventType.SHUTDOWN)

    def __call__(self: _T, app: object) -> _T:
        return self


class Lifespan(BaseRoute):
    def __init__(
        self,
        context: typing.AsyncContextManager = None,
        **handlers: typing.List[typing.Callable],
    ) -> None:
        assert not (
            context is None and handlers is None
        ), "Use either `context` or `**handlers`"
        self.handlers = {et: handlers.get(str(et), []) for et in list(EventType)}
        if context is None:
            self.context = _DefaultLifespan(self)
        elif inspect.isasyncgenfunction(context):
            warnings.warn(
                "async generator function lifespans are deprecated, "
                "use an @contextlib.asynccontextmanager function instead",
                DeprecationWarning,
            )
            self.context = contextlib.asynccontextmanager(context)
        elif inspect.isgeneratorfunction(context):
            warnings.warn(
                "generator function lifespans are deprecated, "
                "use an @contextlib.asynccontextmanager function instead",
                DeprecationWarning,
            )
            self.context = _wrap_gen_lifespan_context(context)
        else:
            self.context = context

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = False
        app = scope.get("app")
        try:
            await receive()
            async with self.context(app):
                await send({"type": EventType.STARTUP.complete})
                started = True
                await receive()
        except BaseException:
            exc = traceback.format_exc()
            if started:
                msg_type = f"{EventType.SHUTDOWN.lifespan}.failed"
            else:
                msg_type = f"{EventType.STARTUP.lifespan}.failed"
            await send({"type": msg_type, "message": exc})
            raise
        else:
            await send({"type": EventType.SHUTDOWN.complete})

    def matches(self, scope: Scope) -> typing.Tuple[Match, Scope]:
        if scope["type"] == "lifespan":
            return Match.FULL, {}
        return Match.NONE, {}

    def add_event_handler(self, event_type: str, func: typing.Callable) -> None:
        self.handlers[EventType(event_type)].append(func)

    def on_event(self, event_type: str) -> typing.Callable:
        def decorator(func):
            self.add_event_handler(event_type, func)
            return func

        return decorator

    async def handler(self, event_type: EventType) -> None:
        for handler in self.handlers.get(event_type, []):
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()
