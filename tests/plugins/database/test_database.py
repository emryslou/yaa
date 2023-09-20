from yast.applications import Yast


def test_get_database_backend():
    from yast.plugins.database import get_database_backend, DatabaseURL

    get_database_backend(DatabaseURL("mysql+pymysql://localhost:3306"))
    get_database_backend(DatabaseURL("postgresql://localhost:5432"))
