import asyncio
import enum
import typing

from yast.types import ASGIApp, ASGIInstance, Receive, Scope, Send

STATE_TRANSITION_ERROR = "Got invalid state transition on lifespan protocal"


class EventType(enum.Enum):
    STARTUP: str = "startup"
    SHUTDOWN: str = "shutdown"

    def __str__(self) -> str:
        return self.value

    @property
    def lifespan(self) -> str:
        return "lifespan.%s" % self.value

    @property
    def complete(self) -> str:
        return "%s.complete" % self.lifespan


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
        self.send_buffer = asyncio.Queue()
        self.receive_buffer = asyncio.Queue()

    async def __call__(self, receive: Receive, send: Send) -> None:
        loop = asyncio.get_event_loop()
        inner_task = loop.create_task(self.run_inner())
        try:
            for event_type in self.handlers.keys():
                message = await receive()
                assert message["type"] == event_type.lifespan
                await self.handler(event_type)

                await self.receive_buffer.put(message)
                message = await self.send_buffer.get()
                if message is None:
                    inner_task.result()
                assert message["type"] == event_type.complete
                await send({"type": message["type"]})
            # endfor
        except BaseException as exc:
            import sys
            import traceback

            print("exception -- 01", exc)
            traceback.print_tb(exc.__traceback__, file=sys.stdout)
        finally:
            await inner_task

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
