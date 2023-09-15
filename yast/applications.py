import typing

from yast.datastructures import URLPath
from yast.middlewares import BaseHttpMiddleware
from yast.routing import BaseRoute, Router
from yast.types import ASGIApp, ASGIInstance, Scope


class Yast(object):
    def __init__(self, debug: bool = False, template_directory: str = None) -> None:
        self._debug = debug
        self.router = Router(routes=[])
        self.app = self.router
        self.middleware_app = self.app
        self.config = {
            "template_directory": template_directory,
        }
        self.__init_plugins__()

    def __init_plugins__(self):
        from yast.plugins import exceptions as plugin_exceptions, lifespan as plugin_lifespan

        plugin_exceptions.plugin_init(self)
        plugin_lifespan.plugin_init(self)

        self.schema_generator = None
        self.template_env = self.load_template_env(self.config["template_directory"])

    @property
    def routes(self) -> typing.List[BaseRoute]:
        return self.router.routes

    @property
    def schema(self) -> dict:
        assert self.schema_generator is not None
        return self.schema_generator.get_schema(self.routes)

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, val: bool) -> None:
        self._debug = val
        self.exception_middleware.debug = val
        self.error_middleware.debug = val

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        self.router.mount(path, app=app, name=name)

    def add_route(
        self,
        path: str,
        route: typing.Union[typing.Callable, BaseRoute],
        methods: list[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ) -> None:
        self.router.add_route(
            path, route, methods=methods, name=name, include_in_schema=include_in_schema
        )

    def add_route_ws(
        self, path: str, route: typing.Union[typing.Callable, BaseRoute]
    ) -> None:
        self.router.add_route_ws(path, route)

    def add_middleware(
        self,
        middleware_class_or_func: typing.Union[type, typing.Callable],
        **kwargs: typing.Any
    ) -> None:
        self.middleware_app = middleware_class_or_func(self.middleware_app, **kwargs)

    def route(
        self,
        path: str,
        methods: list[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ) -> typing.Callable:
        def decorator(func):
            self.router.add_route(
                path, func, methods, name=name, include_in_schema=include_in_schema
            )
            return func

        return decorator

    def ws_route(self, path: str, name: str = None) -> typing.Callable:
        def decorator(func):
            self.router.add_route_ws(path, func, name=name)
            return func

        return decorator

    def middleware(self, middleware_type: str) -> typing.Callable:
        assert middleware_type == "http", 'Current only middleware("http") is supported'

        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_middleware(BaseHttpMiddleware, dispatch=func)

            return func

        return decorator

    def url_path_for(self, name, **path_params: str) -> URLPath:
        return self.router.url_path_for(name=name, **path_params)

    def load_template_env(self, template_directory: str = None) -> typing.Any:
        if template_directory is None:
            return None

        import jinja2

        @jinja2.pass_context
        def url_for(context: dict, name: str, **path_params: typing.Any) -> str:
            req = context["request"]
            return req.url_for(name, **path_params)

        loader = jinja2.FileSystemLoader(str(template_directory))
        env = jinja2.Environment(loader=loader, autoescape=True)
        env.globals["url_for"] = url_for
        return env

    def get_template(self, name: str) -> typing.Any:
        return self.template_env.get_template(name)

    def __call__(self, scope: Scope) -> ASGIInstance:
        scope["app"] = self
        return self.middleware_app(scope)
