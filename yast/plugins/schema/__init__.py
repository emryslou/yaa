__name__ = "schema"
import functools

from yast.applications import Yast


def plugin_init(app: Yast, config: dict = {}):
    schema_generator = config.get("schema_generator", None)

    def get_schema(app) -> dict:
        schema_generator is not None
        return schema_generator.get_schema(app.routes)

    schema = functools.partial(get_schema, app=app)
    setattr(app, "schema", schema)
