from yaa.types import ASGIApp, Receive, Scope, Send


class Middleware(object):
    def __init__(self, app: ASGIApp, **kwargs) -> None:
        self.app = app

    def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        raise NotImplementedError()  # pragma: nocover
