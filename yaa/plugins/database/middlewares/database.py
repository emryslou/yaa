import asyncio
import typing
import warnings

from yaa.datastructures import DatabaseURL
from yaa.middlewares.core import Middleware
from yaa.plugins.database.drivers.base import (
    DatabaseBackend,
    DatabaseSession,
    DatabaseTransaction,
)
from yaa.plugins.lifespan.types import EventType
from yaa.types import ASGI3App, Message, Receive, Scope, Send


class DatabaseMiddleware(Middleware):
    def __init__(
        self,
        app: ASGI3App,
        database_url: typing.Union[str, DatabaseURL],
        debug: bool = False,
        rollback_on_shutdown: bool = False,
    ) -> None:
        super().__init__(app)
        self.debug = debug
        self.backend = self.get_backend(database_url)
        self.rollback_on_shutdown = rollback_on_shutdown
        self.session: typing.Optional["DatabaseSession"] = None
        self.transaction: typing.Optional["DatabaseTransaction"] = None

    def get_backend(
        self, database_url: typing.Union[str, DatabaseURL]
    ) -> DatabaseBackend:
        if isinstance(database_url, str):
            database_url = DatabaseURL(database_url)

        from yaa.plugins.database import get_database_backend

        return get_database_backend(database_url)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await DatabaseLifespan(
                self.app, startup=[self.startup], shutdown=[self.shutdown]  # type: ignore
            )(scope, receive, send)
            return

        if self.session is not None:
            session = self.session
        else:
            session = self.backend.session()

        scope["database"] = session  # type: ignore[index]

        await self.app(scope, receive, send)

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
    def __init__(
        self, app: ASGI3App, **handlers: typing.List[typing.Coroutine]
    ) -> None:
        self.inner = app
        self.handlers = {
            event_type: handlers.get(str(event_type), [])
            for event_type in list(EventType)
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        _all_event_spans = {et.lifespan: et for et in list(EventType)}

        async def receiver() -> Message:
            message = await receive()
            if message["type"] in _all_event_spans:
                await self.run_handlers(str(_all_event_spans[message["type"]]))

            return message

        await self.inner(scope, receiver, send)

    async def run_handlers(self, event_type: str) -> None:
        for handler in self.handlers.get(EventType(event_type), []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    assert callable(handler)
                    handler()
            except Exception as exc:  # pragram: on cover
                warnings.warn(
                    "database init error, may lead to unusabe, err:" + str(exc)
                )  # pragram: on cover
