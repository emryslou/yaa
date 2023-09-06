from yast import TestClient, Yast
from yast.middlewares import SessionMiddleware
from yast.responses import JSONResponse

app = Yast()
app.add_middleware(SessionMiddleware, secret_key="aaccxx", session_cookie="just")


@app.route("/vs")
def vs(req):
    return JSONResponse({"session": req.session})


@app.route("/us", methods=["POST"])
async def us(req):
    data = await req.json()
    req.session.update(data)
    return JSONResponse({"session": req.session})


@app.route("/cs", methods=["POST"])
async def cs(req):
    req.session.clear()
    return JSONResponse({"session": req.session})


def test_session():
    client = TestClient(app)
    res = client.get("/vs")
    assert res.status_code == 200
    assert res.json() == {"session": {}}

    res = client.post("/us", json={"hello": "session"})
    assert res.status_code == 200
    assert res.json() == {"session": {"hello": "session"}}

    response = client.post("/cs")
    assert response.json() == {"session": {}}
    response = client.get("/vs")
    assert response.json() == {"session": {}}
