from yast.applications import Yast


def test_plugin_init(capsys):
    app = Yast(plugins={"database": {}})

    output = capsys.readouterr()

    assert output.out.strip() == "plugin init"


def test_get_database_backend():
    from yast.plugins.database import get_database_backend, DatabaseURL

    get_database_backend(DatabaseURL("mysql://localhost:3306"))
    get_database_backend(DatabaseURL("postgresql://localhost:5432"))
