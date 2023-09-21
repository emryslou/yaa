import pytest

from yast.applications import Yast


def test_enbale_db_type_mysql():
    from yast.plugins.database import get_database_backend, plugin_init, DatabaseURL

    Yast(plugins={"database": {"enable_db_types": [{"db_type": "mysql"}]}})

    get_database_backend(DatabaseURL("mysql+pymysql://localhost:3306"))
    # todo: need install extra package
    get_database_backend(DatabaseURL("mysql://localhost:3306"))

    with pytest.raises(RuntimeError):
        get_database_backend(DatabaseURL("postgres://localhost:3306"))


def test_enbale_db_type_postgres():
    from yast.plugins.database import get_database_backend, plugin_init, DatabaseURL

    Yast(plugins={"database": {"enable_db_types": [{"db_type": "postgres"}]}})

    get_database_backend(DatabaseURL("postgresql://localhost:5432"))


def test_enbale_db_type_failure_db_type(capsys):
    from yast.plugins.database import get_database_backend, plugin_init, DatabaseURL

    Yast(plugins={"database": {"enable_db_types": [{"db_type": "AAAA"}]}})
    capout = capsys.readouterr()
    assert "db `AAAA` enabled failed" in capout.err


def test_enbale_db_type_failure_requires(capsys):
    from yast.plugins.database import get_database_backend, plugin_init, DatabaseURL

    Yast(
        plugins={
            "database": {
                "enable_db_types": [{"db_type": "mysql", "requires": ["CCCC"]}]
            }
        }
    )
    capout = capsys.readouterr()
    assert "db `mysql` enabled failed" in capout.err
    assert "CCCC" in capout.err


def test_enbale_db_type_custome(capsys, tmpdir):
    import os
    from yast.plugins.database import (
        get_database_backend,
        plugin_init,
        DatabaseURL,
        DatabaseBackend,
    )

    backend_path = os.path.join(tmpdir, "mydata.py")
    mydata = (
        "from yast.plugins.database import DatabaseBackend, DatabaseURL\n"
        "class MydataBackend(DatabaseBackend):\n"
        "    name = 'mydata'\n"
        "    def __init__(self, database_url: DatabaseURL) -> None:\n"
        "        self.databse_url = database_url\n"
        "\n"
        "    def my(self) -> str:\n"
        "        return 'AABBCC'\n"
    )

    with open(backend_path, "w") as bfile:
        bfile.write(mydata)

    Yast(
        plugins={
            "database": {
                "enable_db_types": [
                    {
                        "db_type": "mydata",
                        "requires": ["pymysql"],
                        "package_file": backend_path,
                    }
                ]
            }
        }
    )

    klass = get_database_backend(DatabaseURL("mydata://localhost:5432"))
    assert klass.my() == "AABBCC"
