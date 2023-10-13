import pytest
import pytest_benchmark

# pytest.skip("skipping", allow_module_level=True)

class TestDebug:
    def test_open_file(self, tmpdir):
        from yaa import Yaa
        from yaa.middlewares import Middleware

        class MyMiddleware(Middleware):
            def __init__(self, app, debug=False):
                super().__init__(app)

            async def __call__(self, scope, receive, send):
                await self.app(scope, receive, send)

        def handler_500(req, exc):
            pass

        def handler_403(req, exc):
            pass

        app = Yaa(
            exception_handlers={500: handler_500, 403: handler_403},
            middlewares=[(MyMiddleware, {})],
            plugins={"session": {}},
        )

        @app.exception_handler(Exception)
        def handler_exc(req, exc):
            pass
