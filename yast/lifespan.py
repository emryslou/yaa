import asyncio
import enum
import typing

from yast.types import ASGIApp, Message, Receive, Scope, Send

STATE_TRANSITION_ERROR = "Got invalid state transition on lifespan protocal"


class EventType(enum.Enum):
    STARTUP: str = "startup"
    SHUTDOWN: str = "shutdown"
    CLEANUP: str = "cleanup"

    def __str__(self) -> str:
        return self.value


class LifeSpanHandler(object):
    def __init__(self) -> None:
        self.handlers = {et: [] for et in list(EventType)}

    def on_event(self, event_type: str) -> typing.Callable:
        def decorator(func):
            self.add_event_handler(event_type, func)
            return func

        return decorator

    def add_event_handler(self, event_type: str, func: typing.Callable) -> None:
        event_types = [EventType(event_type)]

        if EventType(event_type) in (EventType.CLEANUP, EventType.SHUTDOWN):
            event_types = [EventType.SHUTDOWN]

        [self.handlers[et].append(func) for et in set(event_types)]

    async def run_handler(self, event_type: EventType) -> None:
        assert (
            event_type in self.handlers
        ), f'EventType "{str(event_type)}" not supported'
        for handler in self.handlers[event_type]:
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()

    def __call__(self, scope: Scope) -> typing.Callable:
        assert scope["type"] == "lifespan"
        return self.run_lifespan

    async def run_lifespan(self, receive: Receive, send: Send):
        for it in self.handlers.keys():
            if it == EventType.CLEANUP:
                continue
            message = await receive()
            await self.run_handler(it)
            await send({"type": f"lifespan.{it.value}.complete"})


class LifeSpanContext(object):
    def __init__(self, app: ASGIApp, **kwargs) -> None:
        self.timeout = {
            et: kwargs.get(f"{et.value}_timeout", 10)
            for et in list(EventType)
            if EventType.CLEANUP != et
        }
        self.events = {
            et: asyncio.Event() for et in list(EventType) if EventType.CLEANUP != et
        }

        self.receive_queue = asyncio.Queue()
        self.asgi = app({"type": "lifespan"})

    def __enter__(self) -> None:
        loop = asyncio.get_event_loop()
        loop.create_task(self.run_lifespan())
        loop.run_until_complete(self.wait_event_type(EventType.STARTUP))

    def __exit__(self, exc_type, exc, tb) -> None:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.wait_event_type(EventType.SHUTDOWN))

    async def run_lifespan(self) -> None:
        try:
            await self.asgi(self.receive, self.send)
        finally:
            [event.set() for event in self.events.values()]

    async def send(self, message: Message) -> None:
        if message["type"] == "lifespan.startup.complete":
            self.events[EventType.STARTUP].set()
        else:
            self.events[EventType.SHUTDOWN].set()

    async def receive(self) -> None:
        return await self.receive_queue.get()

    async def wait_event_type(self, event_type: EventType) -> None:
        await self.receive_queue.put({"type": f"lifespan.{str(event_type)}"})
        await asyncio.wait_for(self.events[event_type].wait(), self.timeout[event_type])
