from yaa.applications import Yaa


def test_init(capsys):
    Yaa(plugins={"http": {"middlewares": {"cors": {}, "httpsredirect": {}}}})
