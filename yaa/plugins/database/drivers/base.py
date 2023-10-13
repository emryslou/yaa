import typing
from types import TracebackType

from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql import ClauseElement

from yaa.types import P


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


class DatabaseBackend(object):
    name: str
    drivers: typing.Dict[str, type["DatabaseBackend"]] = {}

    def __init_subclass__(cls, *args: P.args, **kwargs: P.kwargs) -> None:
        super().__init_subclass__(*args, **kwargs)
        names_ = []  # type: typing.List[str]
        if hasattr(cls, "name"):
            names_.append(cls.name)

        if hasattr(cls, "alias_names"):
            names_.extend(cls.alias_names)

        for name in names_:
            cls.drivers[name] = cls

    async def startup(self) -> None:
        raise NotImplementedError()

    async def shutdown(self) -> None:
        raise NotImplementedError()

    def session(self) -> "DatabaseSession":
        raise NotImplementedError()


class DatabaseSession(object):
    async def fetchall(self, query: ClauseElement) -> typing.Any:
        raise NotImplementedError()

    async def fetchone(self, query: ClauseElement) -> typing.Any:
        raise NotImplementedError()

    async def fetchfield(self, query: ClauseElement, index: int = 0) -> typing.Any:
        row = await self.fetchone(query)
        return row[index]

    async def execute(self, query: ClauseElement) -> None:
        raise NotImplementedError()

    async def executemany(self, query: ClauseElement, values: list) -> None:
        raise NotImplementedError()

    def transaction(self) -> "DatabaseTransaction":
        raise NotImplementedError()

    async def acquire_connection(self) -> typing.Any:
        raise NotImplementedError()

    async def release_connection(self) -> None:
        raise NotImplementedError()


class DatabaseTransaction(object):
    async def __aenter__(self) -> None:
        raise NotImplementedError()

    async def __aexit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]] = None,
        exc_value: typing.Optional[BaseException] = None,
        traceback: typing.Optional[TracebackType] = None,
    ) -> None:
        raise NotImplementedError()

    async def start(self) -> None:
        raise NotImplementedError()

    async def commit(self) -> None:
        raise NotImplementedError()

    async def rollback(self) -> None:
        raise NotImplementedError()
