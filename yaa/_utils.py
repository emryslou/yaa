import asyncio
import functools
import typing


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