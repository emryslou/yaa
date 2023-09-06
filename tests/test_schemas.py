from yast import Yast
from yast.endpoints import HttpEndPoint
from yast.schemas import SchemaGenerator

app = Yast()
app.schema_generator = SchemaGenerator(
    {
        "openapi": "3.0.0",
        "info": {
            "title": "Example API",
            "version": "1.0",
        },
    }
)


@app.route("/schema")
class SchemaEndPoint(HttpEndPoint):
    def get(self, req):
        """
        responses:
            200:
                description: SchemaEndPoint
                examples:
                    [{"name": "AAA"}, {"name": "BBB"}]
        """
        pass


def test_schema_generation():
    assert app.schema == {
        "openapi": "3.0.0",
        "info": {
            "title": "Example API",
            "version": "1.0",
        },
        "paths": {
            "/schema": {
                "get": {
                    "responses": {
                        200: {
                            "description": "SchemaEndPoint",
                            "examples": [
                                {"name": "AAA"},
                                {"name": "BBB"},
                            ],
                        }
                    }
                }
            }
        },
    }
