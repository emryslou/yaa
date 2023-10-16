import functools
import typing

from yaa.applications import Yaa
from yaa.plugins import load_middlewares

__name__ = "exceptions"


def plugin_init(app: Yaa, config: dict = {}) -> None:
    assert "middlewares" in config
    assert "exception" in config["middlewares"]
    assert "servererror" in config["middlewares"]

    load_middlewares(app, __package__, config["middlewares"])

    def add_exception_handler(
        exc_class_or_status_code: typing.Union[int, typing.Type[Exception]],
        handler: typing.Callable,
        app: Yaa,
    ) -> None:
        app.exception_handlers[exc_class_or_status_code] = handler
        app.build_middleware_stack()

    def exception_handler(
        exc_class_or_status_code: typing.Union[int, typing.Type[Exception]],
        app: Yaa,
    ) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            app.add_exception_handler(exc_class_or_status_code, func)  # type: ignore
            return func

        return decorator

    app.add_exception_handler = functools.partial(add_exception_handler, app=app)  # type: ignore
    app.exception_handler = functools.partial(exception_handler, app=app)  # type: ignore
