import typing

from yaa.datastructures import URL, Headers
from yaa.middlewares.core import Middleware
from yaa.responses import PlainTextResponse, RedirectResponse, Response
from yaa.types import ASGI3App, Receive, Scope, Send

ENFORCE_DOMAIN_WILDCARD = "Domain wildcard patterns must be like '*.example.com'."


class TrustedHostMiddleware(Middleware):
    def __init__(
        self,
        app: ASGI3App,
        debug: bool = False,
        allowed_hosts: typing.Optional[typing.List[str]] = None,
        www_redirect: bool = True,
    ) -> None:
        super().__init__(app)
        self.debug = debug
        if allowed_hosts is None:
            allowed_hosts = ["*"]
        for pattern in allowed_hosts:
            assert "*" not in pattern[1:], ENFORCE_DOMAIN_WILDCARD
            if pattern.startswith("*") and pattern != "*":
                assert pattern.startswith("*"), ENFORCE_DOMAIN_WILDCARD
        self.allowed_hosts = allowed_hosts
        self.allow_any = "*" in self.allowed_hosts
        self.www_redirect = www_redirect

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and not self.allow_any:
            headers = Headers(scope=scope)
            host = headers.get("host", "").split(":")[0]  # type: ignore
            found_www_redirect = False
            for pattern in self.allowed_hosts:
                if (
                    host == pattern
                    or pattern.startswith("*")
                    and host.endswith(pattern[1:])
                ):
                    break
                elif "www." + host == pattern:
                    found_www_redirect = True
            else:
                res: Response
                if found_www_redirect and self.www_redirect:
                    url = URL(scope=scope)
                    redirect_url = url.replace(netloc="www." + url.netloc)
                    res = RedirectResponse(url=str(redirect_url))
                else:
                    res = PlainTextResponse("Invalid host header", status_code=400)

                await res(scope, receive, send)
                return

        await self.app(scope, receive, send)
