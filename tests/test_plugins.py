from yast import Yast


def test_plugin_init():
    Yast(plugins={"database": {}})
