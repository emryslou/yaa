import asyncio
import typing

from yast.routing import BaseRoute, Match
from yast.types import ASGIInstance, Receive, Scope, Send

from .types import EventType


class Lifespan(BaseRoute):
    def __init__(self, **handlers: typing.List[typing.Callable]) -> None:
        self.handlers = {et: handlers.get(str(et), []) for et in list(EventType)}

    def __call__(self, scope: Scope) -> ASGIInstance:
        return self.asgi

    async def asgi(self, receive: Receive, send: Send) -> None:
        """
        need handle all event: startup, shutdown
        just like:
            message = await receive()
            call_all_event_startup_handlers()
            await send({'type': 'lifespan.startup.complete'})
            message = await receive()
            call_all_event_shutdown_handlers()
            await send({'type': 'lifespan.shutdown.complete'})
        """
        for _ in list(EventType):
            message = await receive()
            event_type = EventType.get_by_lifespan(message["type"])
            await self.handler(event_type)
            await send({"type": event_type.complete})

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
