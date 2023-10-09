import asyncio
import functools
import typing
from asyncio import create_task
from typing import Any, AsyncGenerator, Iterator

import anyio

try:
    import contextvars
except ImportError:  # pragma: no cover
    contextvars = None  # pragma: no cover


async def run_until_first_complete(*args: typing.Tuple[typing.Callable, dict]) -> None:
    async with anyio.create_task_group() as tg:

        async def run(func: typing.Callable[[], typing.Coroutine]) -> None:
            await func()
            tg.cancel_scope.cancel()

        for func, kwargs in args:
            tg.start_soon(run, functools.partial(func, **kwargs))


async def run_in_threadpool(
    func: typing.Callable, *args: typing.Any, **kwargs: typing.Any
) -> typing.Any:
    if contextvars is not None:
        _child = functools.partial(func, *args, **kwargs)
        context = contextvars.copy_context()
        func = context.run
        args = (_child,)
    elif kwargs:  # pragma: no cover
        func = functools.partial(func, **kwargs)

    return await anyio.to_thread.run_sync(func, *args)


class _StopIteration(Exception):
    pass


def _next(iterator: Iterator) -> Any:
    try:
        return next(iterator)
    except StopIteration:
        raise _StopIteration


async def iterate_in_threadpool(iterator: Iterator) -> AsyncGenerator:
    while True:
        try:
            yield await anyio.to_thread.run_sync(_next, iterator)
        except _StopIteration:
            break
