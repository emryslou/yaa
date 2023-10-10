from yaa import Yaa


def test_plugin_init(client_factory):
    Yaa(plugins={"database": {}})
