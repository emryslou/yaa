# type: ignore

from yaa.applications import Yaa

from .graphql import GraphQLApp

__name__ = "graphql"


def plugin_init(app: Yaa, config: dict = {}) -> None:
    if "routes" in config:
        for route_cfg in config["routes"]:
            route_cfg["route"] = GraphQLApp(route_cfg.pop("schema"))
            app.add_route(**route_cfg)
