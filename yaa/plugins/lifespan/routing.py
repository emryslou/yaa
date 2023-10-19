import contextlib
import functools
import inspect
import traceback
import types
import typing
import warnings

from yaa._utils import is_async_callable
from yaa.routing import BaseRoute, Match, Router
from yaa.types import (
    Lifespan as LifespanType,
    Receive,
    Scope,
    Send,
    StatelessLifespan,
)

from .types import EventType

_T = typing.TypeVar("_T")
_TDefaultLifespan = typing.TypeVar("_TDefaultLifespan", bound="_DefaultLifespan")


class _AsyncLiftContextManager(typing.AsyncContextManager[_T]):
    def __init__(self, cm: typing.ContextManager[_T]):
        self._cm = cm

    async def __aenter__(self) -> _T:
        return self._cm.__enter__()

    async def __aexit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType],
    ) -> typing.Optional[bool]:
        return self._cm.__exit__(exc_type, exc_value, traceback)


def _wrap_gen_lifespan_context(
    lifespan_context: typing.Callable[[typing.Any], typing.Generator]
) -> typing.Callable[[typing.Any], typing.AsyncContextManager]:
    cmgr = contextlib.contextmanager(lifespan_context)

    @functools.wraps(cmgr)
    def wrapper(app: typing.Any) -> _AsyncLiftContextManager:
        return _AsyncLiftContextManager(cmgr(app))

    return wrapper


class _DefaultLifespan(object):
    def __init__(self, router: "Router"):
        self._router = router
        self._state: typing.Optional[typing.Dict[str, typing.Any]] = None

    async def __aenter__(self) -> None:
        await self._router.handler(EventType.STARTUP, state=self._state)  # type: ignore

    async def __aexit__(self, *exc_info: object) -> None:
        await self._router.handler(EventType.SHUTDOWN, state=self._state)  # type: ignore

    def __call__(
        self: _TDefaultLifespan,
        app: object,
        state: typing.Optional[typing.Dict[str, typing.Any]],
    ) -> _TDefaultLifespan:
        self._state = state
        return self


class Lifespan(BaseRoute):
    def __init__(
        self,
        context: typing.Optional[LifespanType] = None,
        **handlers: typing.List[typing.Callable],
    ) -> None:
        assert not (
            context is None and handlers is None
        ), "Use either `context` or `**handlers`"
        self.handlers = {et: handlers.get(str(et), []) for et in list(EventType)}
        if context is None:
            self.context: LifespanType = _DefaultLifespan(self)  # type: ignore
        elif inspect.isasyncgenfunction(context):
            warnings.warn(
                "async generator function lifespans are deprecated, "
                "use an @contextlib.asynccontextmanager function instead",
                DeprecationWarning,
            )
            self.context = contextlib.asynccontextmanager(context)  # type: ignore
        elif inspect.isgeneratorfunction(context):
            warnings.warn(
                "generator function lifespans are deprecated, "
                "use an @contextlib.asynccontextmanager function instead",
                DeprecationWarning,
            )
            self.context = _wrap_gen_lifespan_context(context)  # type: ignore
        else:
            self.context = context  # type: ignore

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = False
        app = scope.get("app")

        state = scope.get("state", None)
        await receive()
        lifespan_needs_state = len(inspect.signature(self.context).parameters) == 2
        server_supports_state = state is not None
        if lifespan_needs_state and not server_supports_state:
            raise RuntimeError(
                'The server does not support "state" in the lifespan scope'
            )

        try:
            context: LifespanType
            if lifespan_needs_state:
                context = functools.partial(self.context, state=state)
            else:
                context = typing.cast(StatelessLifespan, self.context)

            async with context(app):
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
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_event_handler(event_type, func)
            return func

        return decorator

    async def handler(
        self,
        event_type: EventType,
        state: typing.Optional[typing.Dict[str, typing.Any]],
    ) -> None:
        for handler in self.handlers.get(event_type, []):
            handler_sig = inspect.signature(handler)
            if len(handler_sig.parameters) == 1 and state is not None:
                handler = functools.partial(handler, state)
            if is_async_callable(handler):
                await handler()
            else:
                handler()
