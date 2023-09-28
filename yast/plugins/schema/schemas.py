import inspect
import typing

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # pragma: no cover

from yast.requests import Request
from yast.responses import Response
from yast.routing import BaseRoute, Mount, Route


class EndPointInfo(typing.NamedTuple):
    path: str
    http_method: str
    func: typing.Callable


class BaseSchemaGenerator(object):
    def get_schema(self, routes: typing.List[BaseRoute]) -> dict:
        raise NotImplementedError()  # pragma: no cover

    def get_endpoints(
        self, routes: typing.List[BaseRoute], parent_path: str = ""
    ) -> typing.List[EndPointInfo]:
        endpoints_info = []
        for route in routes:
            if isinstance(route, Mount):
                sub_routes = route.routes or []
                endpoints_info.extend(
                    self.get_endpoints(routes=sub_routes, parent_path=route.path)
                )

            elif not isinstance(route, Route) or not route.include_in_schema:
                continue

            elif inspect.isfunction(route.endpoint) or inspect.ismethod(route.endpoint):
                for method in route.methods or ["GET"]:
                    if method == "HEAD":
                        continue
                    endpoints_info.append(
                        EndPointInfo(
                            "".join((parent_path, route.path)),
                            method.lower(),
                            route.endpoint,
                        )
                    )
            else:
                methods = ["get", "post", "put", "patch", "delete", "options"]
                for method in methods:
                    if not hasattr(route.endpoint, method):
                        continue
                    func = getattr(route.endpoint, method)
                    endpoints_info.append(
                        EndPointInfo(
                            "".join((parent_path, route.path)), method.lower(), func
                        )
                    )
            # endif
        # endfor
        return endpoints_info

    def parse_docstring(self, func_or_method: typing.Callable) -> dict:
        docstring = func_or_method.__doc__
        if not docstring:
            return {}

        assert yaml is not None, "`pyyaml` must be installed to use OpenAPIResponse"
        docstring = docstring.split("----")[-1]
        parsed = yaml.safe_load(docstring)

        if not isinstance(parsed, dict):
            return {}

        return parsed

    def response(self, request: Request) -> Response:
        routes = request.app.routes
        schema = self.get_schema(routes=routes)
        return OpenAPIResponse(content=schema)


class SchemaGenerator(BaseSchemaGenerator):
    def __init__(self, base_schema: dict) -> None:
        self.base_schema = base_schema

    def get_schema(self, routes: typing.List[BaseRoute]) -> dict:
        schema = dict(self.base_schema)
        schema.setdefault("paths", {})
        endpoints_info = self.get_endpoints(routes)

        for endpoint in endpoints_info:
            parsed = self.parse_docstring(endpoint.func)
            if not parsed:
                continue

            if endpoint.path not in schema["paths"]:
                schema["paths"][endpoint.path] = {}

            schema["paths"][endpoint.path][endpoint.http_method] = parsed
        # endfor

        return schema


class OpenAPIResponse(Response):
    media_type = "application/vnd.oai.openapi"

    def render(self, content: typing.Any) -> bytes:
        assert yaml is not None, "`pyyaml` must be installed to use OpenAPIResponse"
        assert isinstance(
            content, dict
        ), "The schema passed to OpenAPIResponse should be a dict"

        return yaml.dump(content, default_flow_style=False).encode("utf-8")
