import functools
import typing

from yast.applications import Yast
from yast.plugins import load_middlewares

__name__ = "exceptions"


def plugin_init(app: Yast, config: dict = {}) -> None:
    assert "middlewares" in config
    assert "exception" in config["middlewares"]
    assert "servererror" in config["middlewares"]

    load_middlewares(app, __package__, config["middlewares"])

    def add_exception_handler(
        exc_class_or_status_code: typing.Union[int, typing.Type[Exception]],
        handler: typing.Callable,
        app: Yast,
    ) -> None:
        app.exception_handlers[exc_class_or_status_code] = handler
        app.build_middleware_stack()

    def exception_handler(
        exc_class_or_status_code: typing.Union[int, typing.Type[Exception]], app: Yast
    ) -> typing.Callable:
        def decorator(func):
            app.add_exception_handler(exc_class_or_status_code, func)
            return func

        return decorator

    app.add_exception_handler = functools.partial(add_exception_handler, app=app)
    app.exception_handler = functools.partial(exception_handler, app=app)
