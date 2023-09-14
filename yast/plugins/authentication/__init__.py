from yast.applications import Yast


def plugin_init(app: Yast, config: dict = {}):
    print("authentication init")
