import graphene

try:
    from graphql.execution.executors.asyncio import AsyncioExecutor
except ImportError:  # pragma: nocover
    pass  # pragma: nocover

from yast import TestClient, Yast
from yast.datastructures import Headers
from yast.graphql import GraphQLApp


class FakeAuthMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, scope):
        headers = Headers(scope=scope)
        scope["user"] = (
            "Zhangsan" if headers.get("Authorization") == "Bearer 123" else None
        )

        return self.app(scope)


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


def test_init():
    _ = GraphQLApp(schema=schema)


def test_get():
    res = client.get("/?query={hello}")
    assert res.status_code == 200
    assert res.json() == {"data": {"hello": "Hello stranger"}, "errors": None}


def test_post():
    res = client.post("/?query={hello}")
    assert res.status_code == 200
    assert res.json() == {"data": {"hello": "Hello stranger"}, "errors": None}


def test_json():
    res = client.post(
        "/", data="{hello}", headers={"Content-Type": "application/graphql"}
    )
    assert res.status_code == 200
    assert res.json() == {"data": {"hello": "Hello stranger"}, "errors": None}


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
    assert response.json() == {"data": {"hello": "Hello stranger"}, "errors": None}


class AsyncQuery(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value="stranger"))

    async def resolve_hello(self, info, name):
        return "Hello " + name


async_schema = graphene.Schema(query=AsyncQuery)
async_app = GraphQLApp(schema=async_schema, executor=AsyncioExecutor())


def test_graphql_async():
    client = TestClient(async_app)
    response = client.get("/?query={ hello }")
    assert response.status_code == 200
    assert response.json() == {"data": {"hello": "Hello stranger"}, "errors": None}


def test_context():
    app = Yast()
    app.add_middleware(FakeAuthMiddleware)
    app.add_route("/", GraphQLApp(schema=schema))
    client = TestClient(app)
    res = client.post(
        "/", json={"query": "{whoami}"}, headers={"Authorization": "Bearer 123"}
    )
    assert res.status_code == 200
    assert res.json() == {"data": {"whoami": "Zhangsan"}, "errors": None}
