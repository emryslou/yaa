import functools
import typing

from yast.requests import Request
from yast.responses import Response


def transaction(func: typing.Callable) -> typing.Callable:
    @functools.wraps(func)
    async def wrapper(req: Request) -> Response:
        async with req.database.transaction():
            return await func(req)

    return wrapper
