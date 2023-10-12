import functools
import typing

import anyio

from yaa.types import P, T


async def run_until_first_complete(*args: typing.Tuple[typing.Callable, dict]) -> None:
    async with anyio.create_task_group() as tg:

        async def run(func: typing.Callable[[], typing.Coroutine]) -> None:
            await func()
            tg.cancel_scope.cancel()

        for func, kwargs in args:
            tg.start_soon(run, functools.partial(func, **kwargs))


async def run_in_threadpool(
    func: typing.Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    if kwargs:  # pragma: no cover
        func = functools.partial(func, **kwargs)

    return await anyio.to_thread.run_sync(func, *args)


class _StopIteration(Exception):
    pass


def _next(iterator: typing.Iterator[T]) -> T:
    try:
        return next(iterator)
    except StopIteration:
        raise _StopIteration


async def iterate_in_threadpool(
    iterator: typing.Iterator[T],
) -> typing.AsyncIterator[T]:
    while True:
        try:
            yield await anyio.to_thread.run_sync(_next, iterator)
        except _StopIteration:
            break
