from yaa import Yaa, TestClient
from yaa.requests import Request
from yaa.responses import PlainTextResponse


def test_trace():
    app = Yaa(plugins={"logging": {"middlewares": {"trace": {}}}})

    @app.route("/")
    async def home(req: Request):
        return PlainTextResponse("trace-id:" + req._scope["trace_id"])

    client = TestClient(app)
    res = client.get("/")

    assert "x-trace-id" in res.headers
    _trace_id = res.headers["x-trace-id"]
    assert res.status_code == 200
    assert res.text == "trace-id:" + _trace_id

    client = TestClient(app)
    res = client.get("/", headers={"X-Trace-Id": "aaa"})

    assert "x-trace-id" in res.headers
    _trace_id = res.headers["x-trace-id"]
    assert res.status_code == 200
    assert res.text == "trace-id:aaa"
