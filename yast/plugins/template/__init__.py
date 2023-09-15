from yast.applications import Yast


def plugin_init(app: Yast, config={}) -> None:
    print("template init")
