from yast.types import ASGIApp, ASGIInstance, Scope


class Middleware(object):
    def __init__(self, app: ASGIApp, **kwargs) -> None:
        self.app = app

    def __call__(self, scope: Scope) -> ASGIInstance:
        raise NotImplementedError()  # pragma: nocover
