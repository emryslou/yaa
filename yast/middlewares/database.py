import asyncio
import typing

from yast.database import DatabaseBackend
from yast.datastructures import DatabaseURL
from yast.middlewares.core import Middleware
from yast.middlewares.lifespan import EventType
from yast.types import ASGIApp, ASGIInstance, Message, Receive, Scope, Send


class DatabaseMiddleware(Middleware):
    def __init__(
        self,
        app: ASGIApp,
        database_url: typing.Union[str, DatabaseURL],
        rollback_on_shutdown: bool,
    ) -> None:
        super().__init__(app)
        self.backend = self.get_backend(database_url)
        self.rollback_on_shutdown = rollback_on_shutdown
        self.session = None
        self.transaction = None

    def get_backend(
        self, database_url: typing.Union[str, DatabaseURL]
    ) -> DatabaseBackend:
        if isinstance(database_url, str):
            database_url = DatabaseURL(database_url)

        from yast.database import get_database_backend

        return get_database_backend(database_url)

    def __call__(self, scope: Scope) -> ASGIInstance:
        if scope["type"] == "lifespan":
            return DatabaseLifespan(
                self.app, scope, startup=[self.startup], shutdown=[self.shutdown]
            )

        if self.session is not None:
            session = self.session
        else:
            session = self.backend.session()

        scope["database"] = session

        return self.app(scope)

    async def startup(self) -> None:
        await self.backend.startup()
        if self.rollback_on_shutdown:
            self.session = self.backend.session()
            self.transaction = self.session.transaction()
            await self.transaction.start()

    async def shutdown(self) -> None:
        if self.rollback_on_shutdown:
            assert self.session is not None
            assert self.transaction is not None
            await self.transaction.rollback()
        await self.backend.shutdown()


class DatabaseLifespan(object):
    def __init__(self, app: ASGIApp, scope: Scope, **handlers: typing.Callable) -> None:
        self.inner = app(scope)
        self.handlers = {
            event_type: handlers.get(str(event_type), [])
            for event_type in list(EventType)
        }

    async def __call__(self, receive: Receive, send: Send) -> None:
        _all_event_spans = {et.lifespan: et for et in list(EventType)}

        async def receiver() -> Message:
            message = await receive()
            if message["type"] in _all_event_spans:
                await self.run_handlers(_all_event_spans[message["type"]])

            return message

        await self.inner(receiver, send)

    async def run_handlers(self, event_type: str) -> None:
        for handler in self.handlers.get(EventType(event_type), []):
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()
