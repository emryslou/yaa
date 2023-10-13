__name__ = "schema"
import functools

from yaa.applications import Yaa


def plugin_init(app: Yaa, config: dict = {}) -> None:
    schema_generator = config.get("schema_generator", None)

    def get_schema(app: Yaa) -> dict:
        schema_generator is not None
        return schema_generator.get_schema(app.routes)

    schema = functools.partial(get_schema, app=app)
    setattr(app, "schema", schema)
