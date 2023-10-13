import functools
import typing

from yaa.applications import Yaa

from .types import EventType

__name__ = "lifespan"


def plugin_init(app: Yaa, config: dict = {}) -> None:
    from .routing import Lifespan

    handlers = config.get("event_handlers", {})
    context = config.get("context", None)
    lifespan = Lifespan(context=context, **handlers)

    def on_event(event_type: EventType, cls: Yaa) -> None:
        lifespan.on_event(str(event_type))

    def add_event_handler(event_type: EventType, func: typing.Callable, cls: Yaa) -> None:
        lifespan.add_event_handler(str(event_type), func)

    app.router.lifespan = lifespan
    
    setattr(app, "on_event", functools.partial(on_event, cls=app))
    setattr(app, "add_event_handler", functools.partial(add_event_handler, cls=app))
