import functools
import typing

from yaa.requests import Request
from yaa.responses import Response


def transaction(func: typing.Callable) -> typing.Callable:
    @functools.wraps(func)
    async def wrapper(req: Request) -> Response:
        async with req.database.transaction():
            return await func(req)

    return wrapper
