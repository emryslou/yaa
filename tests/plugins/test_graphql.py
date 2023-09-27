import graphene
import pytest

try:
    from graphql.execution.executors.asyncio import AsyncioExecutor
except ImportError:  # pragma: nocover
    pass  # pragma: nocover

from yast import TestClient, Yast
from yast.datastructures import Headers
from yast.middlewares import Middleware
from yast.plugins.graphql import GraphQLApp


class FakeAuthMiddleware(Middleware):
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = Headers(scope=scope)
        scope["user"] = (
            "Zhangsan" if headers.get("Authorization") == "Bearer 123" else None
        )
        await self.app(scope, receive, send)


class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value="stranger"))

    whoami = graphene.String()

    def resolve_hello(self, info, name):
        return "Hello " + name

    def resolve_whoami(self, info):
        return (
            "whaaaat"
            if info.context["request"]["user"] is None
            else info.context["request"]["user"]
        )


schema = graphene.Schema(query=Query)
app = GraphQLApp(schema=schema)
client = TestClient(app)


def test_get():
    res = client.get("/?query={hello}")
    assert res.status_code == 200
    assert res.json() == {"data": {"hello": "Hello stranger"}}


def test_post():
    res = client.post("/?query={hello}")
    assert res.status_code == 200
    assert res.json() == {"data": {"hello": "Hello stranger"}}


def test_json():
    res = client.post(
        "/", data="{hello}", headers={"Content-Type": "application/graphql"}
    )
    assert res.status_code == 200
    assert res.json() == {"data": {"hello": "Hello stranger"}}


def test_post_invalid_media_type():
    import yast.status

    res = client.post("/", data="{hello}", headers={"Content-Type": "error"})
    assert res.status_code == yast.status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert res.text == "Unsupported Media Type"


def test_no_query():
    import yast.status

    res = client.get("/")
    assert res.status_code == yast.status.HTTP_400_BAD_REQUEST
    assert res.text == "No Graphql query found in the request"


def test_invalid_field():
    import yast.status

    res = client.post("/", json={"query": "{err}"})
    assert res.status_code == yast.status.HTTP_400_BAD_REQUEST
    assert res.json() == {
        "data": None,
        "errors": [
            {
                "locations": [{"column": 2, "line": 1}],
                "message": 'Cannot query field "err" on type "Query".',
            }
        ],
    }


def test_graphiql_get():
    response = client.get("/", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text


def test_add_graphql_route():
    from yast import Yast

    app = Yast()
    app.add_route("/", GraphQLApp(schema=schema))
    client = TestClient(app)
    response = client.get("/?query={ hello }")
    assert response.status_code == 200
    assert response.json() == {"data": {"hello": "Hello stranger"}}


class AsyncQuery(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value="stranger"))

    async def resolve_hello(self, info, name):
        return "Hello " + name


async_schema = graphene.Schema(query=AsyncQuery)


@pytest.mark.timeout(20)
def test_graphql_async():
    app = Yast()
    app.add_route("/", GraphQLApp(schema=async_schema, executor=AsyncioExecutor()))
    client = TestClient(app)
    response = client.get("/?query={ hello }")
    assert response.status_code == 200
    assert response.json() == {"data": {"hello": "Hello stranger"}}


def test_graphql_async_cls():
    client = TestClient(GraphQLApp(schema=async_schema, executor_class=AsyncioExecutor))
    response = client.get("/?query={ hello }")
    assert response.status_code == 200
    assert response.json() == {"data": {"hello": "Hello stranger"}}


@pytest.mark.skip("batch test skip it")
def test_context():
    ## middlewares=[(FakeAuthMiddleware, {})]
    graphql_app = Yast(middlewares=[(FakeAuthMiddleware, {})])
    graphql_app.add_route("/", GraphQLApp(schema=schema))
    client = TestClient(graphql_app)
    res = client.post(
        "/", json={"query": "{whoami}"}, headers={"Authorization": "Bearer 123"}
    )
    assert res.status_code == 200
    assert res.json() == {"data": {"whoami": "Zhangsan"}}


def test_app_plugin():
    app = Yast(
        plugins={
            "graphql": {
                "routes": [
                    {
                        "path": "/",
                        "schema": schema,
                        "methods": ["GET", "POST"],
                    }
                ]
            }
        }
    )
    client = TestClient(app)
    response = client.get("/?query={ hello }")
    assert response.status_code == 200
    assert response.json() == {"data": {"hello": "Hello stranger"}}
