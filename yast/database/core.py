import functools
import typing
from types import TracebackType

from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql import ClauseElement

from yast.requests import Request
from yast.responses import Response


def compile(query: ClauseElement, dialect: Dialect) -> typing.Tuple[str, list]:
    compiled = query.compile(dialect=dialect)
    compile_params = sorted(compiled.params.items())

    mapping = {key: "$" + str(i) for i, (key, _) in enumerate(compile_params, start=1)}
    compiled_query = compiled.string % mapping

    processors = compiled._bind_processors
    args = [
        processors[key](val) if key in processors else val
        for key, val in compile_params
    ]

    return compiled_query, args


def transaction(func: typing.Callable) -> typing.Callable:
    @functools.wraps(func)
    async def wrapper(req: Request) -> Response:
        async with req.database.transaction():
            return await func(req)

    return wrapper


class DatabaseBackend(object):
    async def startup(self) -> None:
        raise NotImplementedError()  # pragma: nocover

    async def shutdown(self) -> None:
        raise NotImplementedError()  # pragma: nocover

    def session(self) -> "DatabaseSession":
        raise NotImplementedError()  # pragma: nocover


class DatabaseSession(object):
    async def fetchall(self, query: ClauseElement) -> typing.Any:
        raise NotImplementedError()  # pragma: nocover

    async def fetchone(self, query: ClauseElement) -> typing.Any:
        raise NotImplementedError()  # pragma: nocover

    async def fetchfield(self, query: ClauseElement, index: int = 0) -> typing.Any:
        row = await self.fetchone(query)
        return row[index]

    async def execute(self, query: ClauseElement) -> typing.Any:
        raise NotImplementedError()  # pragma: nocover

    def transaction(self) -> "DatabaseTransaction":
        raise NotImplementedError()  # pragma: nocover


class DatabaseTransaction(object):
    async def __aenter__(self) -> None:
        raise NotImplementedError()  # pragma: nocover

    async def __aexit__(
        self,
        exc_type: typing.Type[BaseException] = None,
        exc_value: BaseException = None,
        traceback: TracebackType = None,
    ) -> None:
        raise NotImplementedError()  # pragma: nocover

    async def start(self) -> None:
        raise NotImplementedError()  # pragma: nocover

    async def commit(self) -> None:
        raise NotImplementedError()  # pragma: nocover

    async def rollback(self) -> None:
        raise NotImplementedError()  # pragma: nocover
