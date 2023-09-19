import functools
import typing

from yast.applications import Yast

__name__ = "template"


def plugin_init(app: Yast, config: dict = {}) -> None:
    def load_template_env(template_directory: str = None) -> typing.Any:
        if template_directory is None:
            return None  # pragma: nocover

        import jinja2

        @jinja2.pass_context
        def url_for(context: dict, name: str, **path_params: typing.Any) -> str:
            req = context["request"]
            return req.url_for(name, **path_params)

        loader = jinja2.FileSystemLoader(str(template_directory))
        env = jinja2.Environment(loader=loader, autoescape=True)
        env.globals["url_for"] = url_for
        return env

    template_env = load_template_env(config["template_directory"])

    def get_template(name: str) -> typing.Any:
        return template_env.get_template(name)

    app.get_template = functools.partial(get_template)
