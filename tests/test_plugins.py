from yaa import Yaa


def test_plugin_init():
    Yaa(plugins={"database": {}})
