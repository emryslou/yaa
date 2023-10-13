import os

import pytest

from yaa import Yaa
from yaa.datastructures import URL
from yaa.plugins.database.decorators import transaction
from yaa.plugins.database.middlewares import DatabaseMiddleware
from yaa.requests import Request
from yaa.responses import JSONResponse

try:
    url = URL("mysql+pymysql://root:password@localhost:3306/test_yaa")
    os.environ["YAST_TEST_DB_MYSQL"] = str(url)
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    sock.connect((url.hostname, url.port))
except Exception as exc:  # pragma: no cover
    pytest.skip(
        f"test db cannot connected {exc}", allow_module_level=True
    )  # pragma: no cover


def test_env():
    assert "YAST_TEST_DB_MYSQL" in os.environ


DATABASE_URL = os.environ["YAST_TEST_DB_MYSQL"]

import sqlalchemy

metadata = sqlalchemy.MetaData()
notes = sqlalchemy.Table(
    "notes",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("text", sqlalchemy.String(64)),
    sqlalchemy.Column("complete", sqlalchemy.Boolean),
)


app = Yaa(
    plugins={
        "database": {
            "enable_db_types": [{"db_type": "mysql"}],
            "middlewares": {
                "database": dict(
                    database_url=DATABASE_URL,
                    rollback_on_shutdown=True,  # todo: if False, isolated_during_test_case and executemany will be fail
                )
            },
        }
    }
)


@pytest.fixture(autouse=True, scope="module")
def create_test_base():
    from yaa.datastructures import DatabaseURL

    url = DatabaseURL(DATABASE_URL)
    database = url.database

    # create database
    url = url.replace(path="/")
    engine = sqlalchemy.create_engine(str(url))
    engine.execute("create database if not exists " + database)

    # reconnect
    url = url.replace(path="/" + database)
    engine = sqlalchemy.create_engine(str(url))
    metadata.create_all(engine)
    yield
    engine.execute("drop table notes")
    engine.execute("drop database if exists " + database)


@app.route("/notes", methods=["GET"])
async def list_notes(req: Request):
    query = notes.select()
    results = await req.database.fetchall(query)
    context = [{"text": item["text"], "complete": item["complete"]} for item in results]

    return JSONResponse(context)


@app.route("/notes", methods=["POST"])
@transaction
async def add_note(req: Request):
    data = await req.json()
    query = notes.insert().values(text=data["text"], complete=data["complete"])
    await req.database.execute(query)
    if "raise_exc" in req.query_params:
        raise RuntimeError()

    return JSONResponse(data)


@app.route("/notes/bulk_create", methods=["POST"])
async def bulk_create_notes(request):
    data = await request.json()
    query = notes.insert()
    await request.database.executemany(query, data)
    return JSONResponse({"notes": data})


@app.route("/notes/{note_id:int}", methods=["GET"])
async def note_row(req: Request):
    note_id = req.path_params["note_id"]
    query = notes.select().where(notes.c.id == note_id)
    reuslt = await req.database.fetchone(query)
    context = {"text": reuslt["text"], "complete": reuslt["complete"]}
    return JSONResponse(context)


@app.route("/notes/{note_id:int}/text", methods=["GET"])
async def note_field(req: Request):
    note_id = req.path_params["note_id"]
    query = sqlalchemy.select([notes.c.text]).where(notes.c.id == note_id)
    db = req.database
    from yaa.plugins.database.drivers.base import DatabaseSession

    assert isinstance(db, DatabaseSession)
    reuslt = await db.fetchfield(query)
    context = {"text": reuslt}

    return JSONResponse(context)


@pytest.mark.timeout(40)
def test_database(client_factory):
    with client_factory(app) as client:
        data = {"text": "add", "complete": True}
        res = client.post("/notes", json=data)
        assert res.status_code == 200
        assert res.json() == data

        with pytest.raises(RuntimeError):
            res = client.post(
                "/notes",
                json={"text": "err", "complete": False},
                params={"raise_exc": "true"},
            )

        res = client.post("/notes", json={"text": "abc deed", "complete": True})
        assert res.status_code == 200

        res = client.get("/notes")
        assert res.status_code == 200
        assert res.json() == [
            {"text": "add", "complete": True},
            {"text": "abc deed", "complete": True},
        ]

        res = client.get("/notes/1")
        assert res.status_code == 200
        assert res.json() == {"text": "add", "complete": True}

        res = client.get("/notes/1/text")
        assert res.status_code == 200
        assert res.json() == {"text": "add"}


def test_database_isolated_during_test_cases(client_factory):
    """
    Using `TestClient` as a context manager
    """
    with client_factory(app) as client:
        response = client.post(
            "/notes", json={"text": "just one note", "complete": True}
        )
        assert response.status_code == 200
        response = client.get("/notes")
        assert response.status_code == 200
        assert response.json() == [{"text": "just one note", "complete": True}]
    with client_factory(app) as client:
        response = client.post(
            "/notes", json={"text": "just two note", "complete": True}
        )
        assert response.status_code == 200
        response = client.get("/notes")
        assert response.status_code == 200
        assert response.json() == [{"text": "just two note", "complete": True}]


def test_database_executemany(client_factory):
    with client_factory(app) as client:
        data = [
            {"text": "buy the milk", "complete": True},
            {"text": "walk the dog", "complete": False},
        ]
        response = client.post("/notes/bulk_create", json=data)
        assert response.status_code == 200
        response = client.get("/notes")
        assert response.status_code == 200
        assert response.json() == [
            {"text": "buy the milk", "complete": True},
            {"text": "walk the dog", "complete": False},
        ]
