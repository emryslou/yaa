import functools
import typing

from yast.applications import Yast

from .middlewares import EventType, LifespanMiddleware


def plugin_init(app: Yast, config: dict = {}) -> None:
    lifespan_middleware = LifespanMiddleware(app=app.middleware_app)

    def on_event(event_type: EventType, cls) -> None:
        return lifespan_middleware.on_event(event_type)

    def add_event_handler(event_type: EventType, func: typing.Callable, cls) -> None:
        lifespan_middleware.add_event_handler(event_type, func)

    app.middleware_app = lifespan_middleware
    app.on_event = functools.partial(on_event, cls=app)
    app.add_event_handler = functools.partial(add_event_handler, cls=app)
