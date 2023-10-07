import functools
import typing

__name__ = "template"

from yast.applications import Yast

from .responses import Jinja2Template

templates = Jinja2Template()


def plugin_init(app: Yast, config: dict = {}) -> None:
    templates.load_env(config.get("template_directory", None))

    def get_template(app, name: str) -> typing.Any:
        return templates.get_template(name)  # pragma: no cover

    app.get_template = functools.partial(get_template, app=app)
