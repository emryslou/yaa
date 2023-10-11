from yaa import Yaa
from yaa.responses import JSONResponse


def view_session(request):
    return JSONResponse({"session": request.session})


async def update_session(request):
    data = await request.json()
    request.session.update(data)
    return JSONResponse({"session": request.session})


async def clear_session(request):
    request.session.clear()
    return JSONResponse({"session": request.session})


def create_app(sess_config: dict = {}):
    app = Yaa(plugins={"http": {"middlewares": {"session": sess_config}}})
    app.add_route("/view_session", view_session)
    app.add_route("/update_session", update_session, methods=["POST"])
    app.add_route("/clear_session", clear_session, methods=["POST"])
    return app


def test_session(client_factory):
    app = create_app({"secret_key": "example"})
    client = client_factory(app)

    response = client.get("/view_session")
    assert response.json() == {"session": {}}


def test_session_expires(client_factory):
    app = create_app({"secret_key": "example", "max_age": -1})
    client = client_factory(app)

    response = client.post("/update_session", json={"some": "data"})
    assert response.json() == {"session": {"some": "data"}}

    response = client.get("/view_session")
    assert response.json() == {"session": {}}


def test_secure_session(client_factory):
    app = create_app({"secret_key": "example", "https_only": True})
    secure_client = client_factory(app, base_url="https://testserver")
    unsecure_client = client_factory(app, base_url="http://testserver")
    response = unsecure_client.get("/view_session")
    assert response.json() == {"session": {}}
    response = unsecure_client.post("/update_session", json={"some": "data"})
    assert response.json() == {"session": {"some": "data"}}
    response = unsecure_client.get("/view_session")
    assert response.json() == {"session": {}}
    response = secure_client.get("/view_session")
    assert response.json() == {"session": {}}
    response = secure_client.post("/update_session", json={"some": "data"})
    assert response.json() == {"session": {"some": "data"}}
    response = secure_client.get("/view_session")
    assert response.json() == {"session": {"some": "data"}}
    response = secure_client.post("/clear_session")
    assert response.json() == {"session": {}}
    response = secure_client.get("/view_session")
    assert response.json() == {"session": {}}


def test_session_cookie_subpath(client_factory):
    import re

    app = create_app({"secret_key": "example", "https_only": True})
    second_app = create_app({"secret_key": "example", "https_only": True})
    app.mount("/second_app", second_app)
    client = client_factory(app, base_url="http://testserver/second_app")
    response = client.post("second_app/update_session", json={"some": "data"})
    cookie = response.headers["set-cookie"]
    cookie_path = re.search(r"; path=(\S+);", cookie).groups()[0]
    assert cookie_path == "/second_app"


def test_session_expired(client_factory):
    from yaa.requests import Request
    import time

    app = create_app({"secret_key": "example", "max_age": 1})

    @app.route("/session/set")
    def sess_set(req: Request):
        req.session.update({"hello": "abcd"})
        return JSONResponse(content="session/set")

    @app.route("/session/get")
    def sess_get(req: Request):
        # req.session.update({'hello': 'abcd'})
        return JSONResponse(content=req.session)

    client = client_factory(app)
    res0 = client.get("/session/set")

    res = client.get(
        "/session/get",
        headers={"Cookie": "session=" + res0.cookies.get_dict()["session"]},
    )
    assert res.cookies.get_dict() != {}

    time.sleep(0.5)
    res = client.get(
        "/session/get",
        headers={"Cookie": "session=" + res.cookies.get_dict()["session"]},
    )
    assert res.cookies.get_dict() != {}

    time.sleep(2)
    res = client.get(
        "/session/get",
        headers={"Cookie": "session=" + res.cookies.get_dict()["session"]},
    )
    assert res.cookies.get_dict() == {}


def test_invalid_session_cookie(client_factory):
    app = create_app({"secret_key": "example"})
    client = client_factory(app)
    response = client.post("/update_session", json={"some": "data"})
    assert response.json() == {"session": {"some": "data"}}
    # we expect it to not raise an exception if we provide a bogus session cookie
    response = client.get("/view_session", cookies={"session": "invalid"})
    assert response.json() == {"session": {}}