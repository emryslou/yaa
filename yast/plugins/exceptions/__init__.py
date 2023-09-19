import functools
import typing

from yast.applications import Yast

from .middlewares.error import ExceptionMiddleware
from .middlewares.server import ServerErrorMiddleware

__name__ = "exceptions"


def plugin_init(app: Yast, config: dict = {}) -> None:
    excmv = ExceptionMiddleware(app=app.middleware_app, debug=app.debug)
    srvmv = ServerErrorMiddleware(app=excmv, debug=app.debug)

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

    app.middleware_app = srvmv
    app.add_exception_handler = functools.partial(add_exception_handler, app=app)
    app.exception_handler = functools.partial(exception_handler, app=app)
