import os
import typing

try:
    import jinja2

    if hasattr(jinja2, "pass_context"):
        pass_context = jinja2.pass_context
    else:
        pass_context = jinja2.contextfunction  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    jinja2 = None  # type: ignore # pragma: no cover


from yaa.background import BackgroundTask
from yaa.datastructures import URL
from yaa.requests import Request

from .responses import TemplateResponse
from .types import TempleteContextProcessor


class Jinja2Template(object):
    @typing.overload
    def __init__(
        self,
        directory: typing.Union[
            str, os.PathLike, typing.Sequence[typing.Union[str, os.PathLike]]
        ],
        *,
        context_processors: typing.Optional[
            typing.List[TempleteContextProcessor]
        ] = None,
        **env_options: typing.Any,
    ) -> None:
        ...

    @typing.overload
    def __init__(
        self,
        *,
        env: "jinja2.Environment",
        context_processors: typing.Optional[
            typing.List[TempleteContextProcessor]
        ] = None,
    ) -> None:
        ...

    def __init__(
        self,
        directory: typing.Optional[
            typing.Union[
                str, os.PathLike, typing.Sequence[typing.Union[str, os.PathLike]]
            ]
        ] = None,
        *,
        context_processors: typing.Optional[
            typing.List[TempleteContextProcessor]
        ] = None,
        env: typing.Optional["jinja2.Environment"] = None,
        **env_options: typing.Any,
    ) -> None:
        assert (
            jinja2 is not None
        ), "package `jinja2` must be installed if use jinja2 template"
        assert directory or env, "either `directory` or `env` argument must be passed"

        self.context_processors = context_processors or []

        if env is not None:
            self.env = env
        else:
            self.env = self.load_env(directory, **env_options)  # type: ignore[arg-type]

    def load_env(
        self, directory: typing.Union[str, os.PathLike], **env_options: typing.Any
    ) -> jinja2.Environment:
        assert os.path.isdir(
            directory
        ), f"template directory `{directory}` is not a directory"

        @pass_context
        def url_for(context: dict, name: str, **path_params: typing.Any) -> URL:
            req = context["request"]
            return req.url_for(name, **path_params)

        loader = jinja2.FileSystemLoader(str(directory))
        env_options.setdefault("loader", loader)
        env_options.setdefault("autoescape", True)
        env = jinja2.Environment(**env_options)  # nosec
        env.globals["url_for"] = url_for

        return env

    def get_template(self, name: str) -> jinja2.Template:
        assert self.env is not None
        return self.env.get_template(name)

    def response(
        self,
        name: str,
        request: Request,
        context: dict = {},
        status_code: int = 200,
        headers: typing.Optional[dict] = None,
        media_type: typing.Optional[str] = None,
        background: typing.Optional[BackgroundTask] = None,
    ) -> TemplateResponse:
        if "request" not in context:
            context["request"] = request
            # raise ValueError('context must include a `request` key')

        req = typing.cast(Request, context["request"])
        for ctxt_proc in self.context_processors:
            context.update(ctxt_proc(req))

        template = self.get_template(name)
        return TemplateResponse(
            template=template,
            context=context,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )
