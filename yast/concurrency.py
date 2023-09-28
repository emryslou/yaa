import asyncio
import functools
import typing

try:
    import contextvars
except ImportError:  # pragma: no cover
    contextvars = None  # pragma: no cover


async def run_until_first_complete(*args: typing.Tuple[typing.Callable, dict]) -> None:
    tasks = [handler(**kwargs) for handler, kwargs in args]

    (done, pending) = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    [task.cancel() for task in pending]
    [task.result() for task in done]


async def run_in_threadpool(
    func: typing.Callable, *args: typing.Any, **kwargs: typing.Any
) -> typing.Any:
    _loop = asyncio.get_event_loop()
    if contextvars is not None:
        _child = functools.partial(func, *args, **kwargs)
        context = contextvars.copy_context()
        func = context.run
        args = (_child,)
    elif kwargs:  # pragma: no cover
        func = functools.partial(func, **kwargs)

    return await _loop.run_in_executor(None, func, *args)
