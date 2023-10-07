import getpass
import typing
import uuid
from types import TracebackType

import aiomysql
from sqlalchemy.dialects.mysql import pymysql
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql import ClauseElement

from yaa.datastructures import DatabaseURL

from .base import DatabaseBackend, DatabaseSession, DatabaseTransaction


class MysqlBackend(DatabaseBackend):
    name = "mysql"
    alias_names = ["mysql+pymysql"]

    def __init__(self, database_url: typing.Union[str, DatabaseURL]) -> None:
        self.database_url = DatabaseURL(database_url)
        self.dialect = self.get_dialect()
        self.pool = None

    def get_dialect(self) -> Dialect:
        return pymysql.dialect(paramstyle="pyformat")

    async def startup(self) -> None:
        db = self.database_url
        self.pool = await aiomysql.create_pool(
            host=db.hostname,
            port=db.port or 3306,
            user=db.username or getpass.getuser(),
            password=db.password or "",
            db=db.database,
        )

    async def shutdown(self) -> None:
        assert self.pool is not None, self.__class__.__name__ + " is not running"
        self.pool.close()
        self.pool = None

    def session(self) -> "MysqlSession":
        assert self.pool is not None, self.__class__.__name__ + " is not running"
        return MysqlSession(self.pool, self.dialect)


class Record(object):
    def __init__(self, row: tuple, result_columns: tuple) -> None:
        self._row = row
        self._result_columns = result_columns
        self._column_map = {
            col[0]: (idx, col) for idx, col in enumerate(self._result_columns)
        }

    def __getitem__(self, key: typing.Union[int, str]) -> typing.Any:
        if isinstance(key, int):
            idx = key
            col = self._result_columns[key]
        else:
            idx, col = self._column_map[key]

        raw = self._row[idx]
        return col[-1].python_type(raw)


class MysqlSession(DatabaseSession):
    def __init__(self, pool: aiomysql.pool.Pool, dialect: Dialect) -> None:
        self.pool = pool
        self.dialect = dialect
        self.conn = None
        self.connection_holders = 0
        self.has_root_transaction = False

    def _compile(self, query: ClauseElement) -> typing.Tuple[str, list, tuple]:
        compiled = query.compile(dialect=self.dialect)
        args = compiled.construct_params()  # todo: method may not found
        return compiled.string, args, compiled._result_columns

    async def fetchall(self, query: ClauseElement) -> typing.Any:
        query, args, result_columns = self._compile(query)

        conn = await self.acquire_connection()
        cursor = await conn.cursor()
        try:
            await cursor.execute(query, args)
            rows = await cursor.fetchall()  # todo: fetchall method not found?
            return [Record(row, result_columns) for row in rows]
        finally:
            await cursor.close()
            await self.release_connection()

    async def fetchone(self, query: ClauseElement) -> typing.Any:
        query, args, result_columns = self._compile(query)

        conn = await self.acquire_connection()
        cursor = await conn.cursor()
        try:
            await cursor.execute(query, args)
            row = await cursor.fetchone()  # todo: fetchall method not found?
            return Record(row, result_columns)
        finally:
            await cursor.close()
            await self.release_connection()

    async def fetchfield(self, query: ClauseElement, index: int = 0) -> typing.Any:
        row = await self.fetchone(query)
        return row[index]

    async def execute(self, query: ClauseElement) -> None:
        query, args, result_columns = self._compile(query)

        conn = await self.acquire_connection()
        cursor = await conn.cursor()
        try:
            await cursor.execute(query, args)
        finally:
            await cursor.close()
            await self.release_connection()

    async def executemany(self, query: ClauseElement, values: list) -> None:
        conn = await self.acquire_connection()
        cursor = await conn.cursor()
        try:
            for item in values:
                squery = query.values(item)
                squery, args, result_columns = self._compile(squery)
                await cursor.execute(squery, args)
        finally:
            await cursor.close()
            await self.release_connection()

    async def acquire_connection(self) -> aiomysql.Connection:
        self.connection_holders += 1
        if self.conn is None:
            self.conn = await self.pool.acquire()
        return self.conn

    async def release_connection(self) -> None:
        self.connection_holders -= 1
        if self.connection_holders == 0:
            await self.pool.release(self.conn)
            self.conn = None

    def transaction(self) -> "DatabaseTransaction":
        return MysqlTransaction(self)


class MysqlTransaction(DatabaseTransaction):
    def __init__(self, sesion: MysqlSession) -> None:
        self.session = sesion
        self.is_root = False

    async def __aenter__(self) -> None:
        await self.start()

    async def __aexit__(
        self,
        exc_type: typing.Type[BaseException] = None,
        exc_value: BaseException = None,
        traceback: TracebackType = None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    async def start(self) -> None:
        if self.session.has_root_transaction is False:
            self.session.has_root_transaction = True
            self.is_root = True

        self.conn = await self.session.acquire_connection()
        if self.is_root:
            await self.conn.begin()
        else:
            id = str(uuid.uuid4()).replace("-", "_")
            self.savepoint_name = f"SAVEPOINT_NAME_{id}"

            cursor = await self.conn.cursor()
            try:
                await cursor.execute(f"SAVEPOINT {self.savepoint_name}")
            finally:
                await cursor.close()

    async def commit(self) -> None:
        if self.is_root:
            await self.conn.commit()
            self.session.has_root_transaction = False
        else:
            cursor = await self.conn.cursor()
            try:
                await cursor.execute(f"RELEASE SAVEPOINT {self.savepoint_name}")
            finally:
                await cursor.close()

        await self.session.release_connection()

    async def rollback(self) -> None:
        if self.is_root:
            await self.conn.rollback()
            self.session.has_root_transaction = False
        else:
            cursor = await self.conn.cursor()
            try:
                await cursor.execute(f"ROLLBACK TO SAVEPOINT {self.savepoint_name}")
            finally:
                await cursor.close()
        await self.session.release_connection()
