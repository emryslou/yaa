import typing

from yast.background import BackgroundTask
from yast.requests import Request
from yast.responses import Response
from yast.types import Receive, Send


class TemplateResponse(Response):
    media_type = "text/html"

    def __init__(
        self,
        template: typing.Any,
        context: dict,
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
        background: BackgroundTask = None,
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

    async def __call__(self, receive: Receive, send: Send) -> None:
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
        await super().__call__(receive, send)
