import os
import typing

from yaa.background import BackgroundTask
from yaa.requests import Request
from yaa.responses import Response
from yaa.types import Receive, Scope, Send

try:
    import jinja2

    if hasattr(jinja2, "pass_context"):
        pass_context = jinja2.pass_context
    else:
        pass_context = jinja2.contextfunction  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    jinja2 = None  # type: ignore # pragma: no cover


class TemplateResponse(Response):
    media_type = "text/html"

    def __init__(
        self,
        template: typing.Any,
        context: dict,
        status_code: int = 200,
        headers: typing.Optional[dict] = None,
        media_type: typing.Optional[str] = None,
        background: typing.Optional[BackgroundTask] = None,
    ) -> None:
        if "request" not in context:
            raise ValueError('context must include a "request" key')

        self.template = template
        self.context = context
        content = template.render(context)
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        req = self.context["request"]
        assert isinstance(req, Request)
        extensions = req.get("extensions", {})
        if "http.response.template" in extensions:
            await send(
                {
                    "type": "http.response.template",
                    "template": self.template,
                    "context": self.context,
                }
            )
        await super().__call__(scope, receive, send)


class Jinja2Template(object):
    def __init__(
        self,
        directory: typing.Optional[typing.Union[str, os.PathLike]] = None,
        **env_options: typing.Any,
    ) -> None:
        assert (
            jinja2 is not None
        ), "package `jinja2` must be installed if use jinja2 template"

        self.env: jinja2.Environment
        if directory is not None:
            self.load_env(directory, **env_options)

    def load_env(
        self, directory: typing.Union[str, os.PathLike], **env_options: typing.Any
    ) -> None:
        assert os.path.isdir(
            directory
        ), f"template directory `{directory}` is not a directory"

        @pass_context
        def url_for(context: dict, name: str, **path_params: typing.Any) -> str:
            req = context["request"]
            return req.url_for(name, **path_params)

        loader = jinja2.FileSystemLoader(str(directory))
        env_options.setdefault("loader", loader)
        env_options.setdefault("autoescape", True)
        env = jinja2.Environment(**env_options) # nosec
        env.globals["url_for"] = url_for

        self.env = env

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
        template = self.get_template(name)
        return TemplateResponse(
            template=template,
            context=context,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )
