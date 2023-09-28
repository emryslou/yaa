import asyncio
import inspect
import traceback
import typing

from yast.applications import Yast
from yast.routing import BaseRoute, Match
from yast.types import Receive, Scope, Send

from .types import EventType


class Lifespan(BaseRoute):
    def __init__(self, context=None, **handlers: typing.List[typing.Callable]) -> None:
        assert not (
            context is None and handlers is None
        ), "Use either `context` or `**handlers`"
        self.handlers = {et: handlers.get(str(et), []) for et in list(EventType)}
        self.context = self.default_context if context is None else context

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        first = True
        app = scope.get("app")
        try:

            async def context_item(app):
                nonlocal first
                assert first, "Lifespan context yielded multiple times."
                first = False
                await send({"type": EventType.STARTUP.complete})
                await receive()

            await receive()
            if inspect.isasyncgenfunction(self.context):
                async for item in self.context(app):
                    await context_item(app)
            else:
                for item in self.context(app):
                    await context_item(app)
        except BaseException:
            if first:
                exc = traceback.format_exc()
                await send(
                    {
                        "type": f"{EventType.STARTUP.lifespan}.failed",
                        "message": exc,
                    }
                )
            raise
        else:
            await send({"type": EventType.SHUTDOWN.complete})

    async def default_context(self, app: Yast) -> typing.AsyncGenerator:
        await self.handler(EventType.STARTUP)
        yield
        await self.handler(EventType.SHUTDOWN)

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
