import asyncio
import typing

from yast.types import ASGIApp, ASGIInstance, Message, Receive, Scope, Send

from .types import EventType

STATE_TRANSITION_ERROR = "Got invalid state transition on lifespan protocal"


class LifespanMiddleware(object):
    def __init__(self, app: ASGIApp, **handlers: typing.List[typing.Callable]) -> None:
        self.app = app
        self.handlers = {et: handlers.get(str(et), []) for et in list(EventType)}

    def add_event_handler(self, event_type: str, func: typing.Callable) -> None:
        self.handlers[EventType(event_type)].append(func)

    def on_event(self, event_type: str) -> typing.Callable:
        def decorator(func):
            self.add_event_handler(event_type, func)
            return func

        return decorator

    def __call__(self, scope: Scope) -> ASGIInstance:
        if scope["type"] == "lifespan":
            return LifespanHandler(self.app, scope, self.handlers)
        return self.app(scope)


class LifespanHandler(object):
    def __init__(
        self,
        app: ASGIApp,
        scope: Scope,
        handlers: typing.Dict[EventType, typing.List[typing.Callable]],
    ) -> None:
        self.inner = app(scope)
        self.handlers = handlers

    async def __call__(self, receive: Receive, send: Send) -> None:
        lifespan = {et.lifespan: et for et in list(EventType)}

        async def receiver() -> Message:
            message = await receive()
            if message["type"] in lifespan:
                await self.handler(lifespan[message["type"]])

            return message

        await self.inner(receiver, send)

    async def run_inner(self) -> None:
        try:
            await self.inner(self.receive_buffer.get, self.send_buffer.put)
        finally:
            await self.send_buffer.put(None)

    async def handler(self, event_type: EventType) -> None:
        for handler in self.handlers.get(event_type, []):
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()
