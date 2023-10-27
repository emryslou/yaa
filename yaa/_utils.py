import asyncio
import functools
import logging
import os
import sys
import typing

from contextlib import contextmanager
from types import TracebackType

if sys.version_info >= (3, 10):
    from typing import TypeGuard
else:
    from typing_extensions import TypeGuard

has_exceptiongroups = True
if sys.version_info < (3, 11):
    try:
        from exceptiongroup import BaseExceptionGroup
    except ImportError:
        has_exceptiongroups = False


def get_plugin_middlewares(package: str, root_path: str = "") -> typing.Dict[str, type]:
    import importlib
    import os

    if not root_path:
        root_path = os.path.join(os.path.dirname(__file__), "plugins")

    module_name = f"{package}.middlewares"
    module = importlib.import_module(module_name)

    middlewares = {
        attr.replace("Middleware", "").lower(): getattr(module, attr)
        for attr in module.__dir__()
        if attr.endswith("Middleware")
    }

    return middlewares


def is_async_callable(obj: typing.Any) -> bool:
    while isinstance(obj, functools.partial):
        obj = obj.func

    return asyncio.iscoroutinefunction(obj) or (
        callable(obj) and asyncio.iscoroutinefunction(obj.__call__)
    )


T_co = typing.TypeVar("T_co", covariant=True)


class AwaitableOrContextManager(typing.Protocol[T_co]):
    def __await__(self) -> typing.Generator[typing.Any, None, T_co]:
        ...  # pragma: no cover

    async def __aenter__(self) -> T_co:
        ...  # pragma: no cover

    async def __aexit__(
        self,
        __exc_type: typing.Optional[typing.Type[BaseException]],
        __exc_value: typing.Optional[BaseException],
        __traceback: typing.Optional[TracebackType],
    ) -> typing.Union[bool, None]:
        ...  # pragma: no cover


class SupportsAsyncClose(typing.Protocol):
    async def close(self) -> None:
        ...  # pragma: no cover


SupportsAsyncCloseType = typing.TypeVar(
    "SupportsAsyncCloseType", bound=SupportsAsyncClose, covariant=False
)


class AwaitableOrContextManagerWrapper(typing.Generic[SupportsAsyncCloseType]):
    __slots__ = ("aw", "entered")

    def __init__(self, aw: typing.Awaitable[SupportsAsyncCloseType]) -> None:
        self.aw = aw

    def __await__(self) -> typing.Generator[typing.Any, None, SupportsAsyncCloseType]:
        return self.aw.__await__()

    async def __aenter__(self) -> SupportsAsyncCloseType:
        self.entered = await self.aw
        return self.entered

    async def __aexit__(self, *args: typing.Any) -> typing.Union[None, bool]:
        await self.entered.close()
        return None

@contextmanager
def collapse_excgroups() -> typing.Generator[None, None, None]:
    try:
        yield
    except BaseException as exc:
        if has_exceptiongroups:
            while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
                exc = exc.exceptions[0]
        raise exc

_handler = logging.StreamHandler(sys.stdout)
_formatter = logging.Formatter("[%(asctime)s][%(levelname)s][%(name)s]%(message)s")
_logger_cache: typing.Dict[str, logging.Logger] = {}


def get_logger(_module: typing.Optional[str] = None) -> logging.Logger:
    global _logger_cache
    _module = "yaa" if not _module else _module
    if _module in _logger_cache:
        logger = _logger_cache[_module]
    else:
        logger = logging.Logger(_module)
        _logger_cache[_module] = logger

    _env_debug = os.environ.get("DEBUG", "False")
    debug = _env_debug.title() == "True"
    if debug:
        _handler.setLevel(logging.DEBUG)
    else:
        _handler.setLevel(logging.ERROR)

    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)

    return logger
