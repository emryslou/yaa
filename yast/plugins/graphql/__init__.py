from yast.applications import Yast

from .graphql import GraphQLApp


def plugin_init(app: Yast, config: dict = {}) -> None:
    if "routes" in config:
        for route_cfg in config["routes"]:
            route_cfg["route"] = GraphQLApp(route_cfg.pop("schema"))
            app.add_route(**route_cfg)
