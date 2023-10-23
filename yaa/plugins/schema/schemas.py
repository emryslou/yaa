import inspect
import re
import typing

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore # pragma: no cover

from yaa.requests import Request
from yaa.responses import Response
from yaa.routing import BaseRoute, Host, Mount, Route


class EndPointInfo(typing.NamedTuple):
    path: str
    http_method: str
    func: typing.Callable


class BaseSchemaGenerator(object):
    """文档生成器"""

    def get_schema(self, routes: typing.List[BaseRoute]) -> dict:
        """获取 scheme 字典
        Args:
            routes: 路由列表

        Return:
            dict

        Raise:
            NotImplementedError
        """
        raise NotImplementedError()  # pragma: no cover

    def get_endpoints(
        self, routes: typing.List[BaseRoute], parent_path: str = ""
    ) -> typing.List[EndPointInfo]:
        """获取节点信息
        Args:
            routes: 路由列表
            parent_path: 上级path

        Return:
            list[EndPointInfo]

        Raise:
            None

        """
        endpoints_info = []
        for route in routes:
            if isinstance(route, (Mount, Host)):
                if isinstance(route, Mount):
                    path = self.__remove_converter(route.path)
                else:
                    path = ""
                endpoints_info.extend(
                    [
                        EndPointInfo(
                            path="".join((path, sub_endpoint.path)),
                            http_method=sub_endpoint.http_method,
                            func=sub_endpoint.func,
                        )
                        for sub_endpoint in self.get_endpoints(
                            routes=(route.routes or [])  # type: ignore[attr-defined]
                        )
                    ]
                )

            elif not isinstance(route, Route) or not route.include_in_schema:
                continue

            elif inspect.isfunction(route.endpoint) or inspect.ismethod(route.endpoint):
                path = self.__remove_converter(route.path)
                for method in route.methods or ["GET"]:
                    if method == "HEAD":
                        continue
                    endpoints_info.append(
                        EndPointInfo(
                            "".join((parent_path, path)),
                            method.lower(),
                            route.endpoint,
                        )
                    )
            else:
                path = self.__remove_converter(route.path)
                methods = ["get", "post", "put", "patch", "delete", "options"]
                for method in methods:
                    if not hasattr(route.endpoint, method):
                        continue
                    func = getattr(route.endpoint, method)
                    endpoints_info.append(
                        EndPointInfo("".join((parent_path, path)), method.lower(), func)
                    )
            # endif
        # endfor
        return endpoints_info

    def __remove_converter(self, path: str) -> str:
        """
        replace /a/b/{a:int} => /a/b/{a}
        """
        return re.sub(r":\w+}", "}", path)

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
    """Api文档生成器
    Attrs:
        base_schema: 基本数据

    """

    def __init__(self, base_schema: dict) -> None:
        """Api文档生成器
        Args:
            base_schema: 基本数据

        Returns:
            None

        Raises:
            None
        """

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
