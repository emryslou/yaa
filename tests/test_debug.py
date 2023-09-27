import pytest
import pytest_benchmark

# pytest.skip("skipping", allow_module_level=True)


def test_open_file(tmpdir):
    from yast import Yast
    from yast.middlewares import Middleware

    class MyMiddleware(Middleware):
        def __init__(self, app):
            super().__init__(app)

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)

    def handler_500(req, exc):
        pass

    def handler_403(req, exc):
        pass

    app = Yast(
        exception_handlers={500: handler_500, 403: handler_403},
        middlewares=[(MyMiddleware, {})],
        plugins={"session": {}},
    )

    @app.exception_handler(Exception)
    def handler_exc(req, exc):
        pass
