from yast.applications import Yast


def test_init(capsys):
    Yast(plugins={"http": {"middlewares": {"cors": {}, "httpsredirect": {}}}})
