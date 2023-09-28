import functools
import typing

from yast.applications import Yast

from .types import EventType

__name__ = "lifespan"


def plugin_init(app: Yast, config: dict = {}) -> None:
    from .routing import Lifespan

    handlers = config.get("event_handlers", {})
    context = config.get("context", None)
    lifespan = Lifespan(context=context, **handlers)

    def on_event(event_type: EventType, cls) -> None:
        return lifespan.on_event(event_type)

    def add_event_handler(event_type: EventType, func: typing.Callable, cls) -> None:
        lifespan.add_event_handler(event_type, func)

    app.router.lifespan = lifespan
    app.on_event = functools.partial(on_event, cls=app)
    app.add_event_handler = functools.partial(add_event_handler, cls=app)
