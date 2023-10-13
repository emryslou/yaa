from yaa.types import ASGI3App, P, Receive, Scope, Send


class Middleware(object):
    def __init__(self, app: ASGI3App, *args: P.args, **kwargs: P.kwargs) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        raise NotImplementedError()  # pragma: nocover
