from yaa import TestClient
from yaa.applications import Yaa
from yaa.endpoints import HttpEndPoint
from yaa.plugins.schema.schemas import OpenAPIResponse, SchemaGenerator

schemas = SchemaGenerator(
    {"openapi": "3.0.0", "info": {"title": "Example API", "version": "1.0"}}
)

app = Yaa(
    plugins={
        "schema": {
            "schema_generator": schemas,
        }
    }
)

sub_app = Yaa()
app.mount("/sub", sub_app)


@app.ws_route("/ws")
def ws(session):
    """ws"""
    pass  # pragma: no cover


@app.route("/users", methods=["GET", "HEAD"])
def list_users(request):
    """
    responses:
      200:
        description: A list of users.
        examples:
          [{"username": "ZS"}, {"username": "Cuihua"}]
    """
    pass  # pragma: no cover


@app.route("/users", methods=["POST"])
def create_user(request):
    """
    responses:
      200:
        description: A user.
        examples:
          {"username": "ZS"}
    """
    pass  # pragma: no cover


@app.route("/orgs")
class OrganisationsEndpoint(HttpEndPoint):
    def get(self, request):
        """
        responses:
          200:
            description: A list of organisations.
            examples:
              [{"name": "Foo Corp."}, {"name": "Acme Ltd."}]
        """
        pass  # pragma: no cover

    def post(self, request):
        """
        responses:
          200:
            description: An organisation.
            examples:
              {"name": "Foo Corp."}
        """
        pass  # pragma: no cover


@app.route("/docstring_sep")
def docstring_sep(req):
    """
    Test
    ----
    responses:
      200:
        description: BBBB
    """
    pass  # pragma: no cover


@app.route("/schema", methods=["GET"], include_in_schema=False)
def schema(request):
    return schemas.response(request)


@sub_app.route("/endpoint")
def subapp_endpoint(req):
    """
    responses:
      200:
        description: AAAA
    """
    pass  # pragma: no cover


def test_schema_generation():
    schema = schemas.get_schema(routes=app.routes)
    assert schema == {
        "openapi": "3.0.0",
        "info": {"title": "Example API", "version": "1.0"},
        "paths": {
            "/orgs": {
                "get": {
                    "responses": {
                        200: {
                            "description": "A list of " "organisations.",
                            "examples": [{"name": "Foo Corp."}, {"name": "Acme Ltd."}],
                        }
                    }
                },
                "post": {
                    "responses": {
                        200: {
                            "description": "An organisation.",
                            "examples": {"name": "Foo Corp."},
                        }
                    }
                },
            },
            "/users": {
                "get": {
                    "responses": {
                        200: {
                            "description": "A list of users.",
                            "examples": [{"username": "ZS"}, {"username": "Cuihua"}],
                        }
                    }
                },
                "post": {
                    "responses": {
                        200: {"description": "A user.", "examples": {"username": "ZS"}}
                    }
                },
            },
            "/docstring_sep": {
                "get": {
                    "responses": {
                        200: {
                            "description": "BBBB",
                        }
                    }
                }
            },
            "/sub/endpoint": {
                "get": {
                    "responses": {
                        200: {
                            "description": "AAAA",
                        }
                    }
                }
            },
        },
    }


def test_schema_generation_legacy():
    app.schema_generator = schemas
    assert app.schema() == schemas.get_schema(routes=app.routes)


EXPECTED_SCHEMA = """
info:
  title: Example API
  version: '1.0'
openapi: 3.0.0
paths:
  /docstring_sep:
    get:
      responses:
        200:
          description: BBBB
  /orgs:
    get:
      responses:
        200:
          description: A list of organisations.
          examples:
          - name: Foo Corp.
          - name: Acme Ltd.
    post:
      responses:
        200:
          description: An organisation.
          examples:
            name: Foo Corp.
  /sub/endpoint:
    get:
      responses:
        200:
          description: AAAA
  /users:
    get:
      responses:
        200:
          description: A list of users.
          examples:
          - username: ZS
          - username: Cuihua
    post:
      responses:
        200:
          description: A user.
          examples:
            username: ZS
"""


def test_schema_endpoint():
    client = TestClient(app)
    response = client.get("/schema")
    assert response.headers["Content-Type"] == "application/vnd.oai.openapi"
    assert response.text.strip() == EXPECTED_SCHEMA.strip()
