import functools
import typing

from yast.applications import Yast
from yast.plugins import load_middlewares

__name__ = "exceptions"


def plugin_init(app: Yast, config: dict = {}) -> None:
    assert "middlewares" in config
    assert "exception" in config["middlewares"]
    assert "servererror" in config["middlewares"]

    middlewares = load_middlewares(
        app, __package__, middlewares_config=config["middlewares"]
    )
    excmv = middlewares["exception"]
    srvmv = middlewares["servererror"]

    def add_exception_handler(
        exc_class_or_status_code: typing.Union[int, typing.Type[Exception]],
        handler: typing.Callable,
        app: Yast,
    ) -> None:
        if exc_class_or_status_code in (500, Exception):
            srvmv.handler = handler
        else:
            excmv.add_exception_handler(exc_class_or_status_code, handler)

    def exception_handler(
        exc_class_or_status_code: typing.Union[int, typing.Type[Exception]], app: Yast
    ) -> typing.Callable:
        def decorator(func):
            app.add_exception_handler(exc_class_or_status_code, func)
            return func

        return decorator

    # app.middleware_app = srvmv
    app.add_exception_handler = functools.partial(add_exception_handler, app=app)
    app.exception_handler = functools.partial(exception_handler, app=app)
