import functools
import typing

__name__ = "template"

from yaa.applications import Yaa

from .template import Jinja2Template

templates: Jinja2Template = None  # type: ignore[assignment]


def plugin_init(app: Yaa, config: dict = {}) -> None:
    if not config:
        return  # pragma: no cover
    global templates
    templates = Jinja2Template(**config)

    def get_template(app: Yaa, name: str) -> typing.Any:
        return templates.get_template(name)  # pragma: no cover

    app.get_template = functools.partial(get_template, app=app)  # type: ignore[attr-defined]


def get_templates() -> Jinja2Template:
    global templates
    return templates
