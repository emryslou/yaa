from yast import TestClient, Yast
from yast.responses import JSONResponse, Response
from yast.routing import Mount, Route, Router


def users(req):
    content = req.path_params.get("username", None)
    if content is None:
        content = "All Users"
    else:
        content = "User %s" % content
    return Response(content, media_type="text/plain")


def test_debug():
    app = Yast()

    client = TestClient(app)

    @app.route("/int/{param:int}", name="int_conv")
    def int_conv(req):
        num = req.path_params["param"]
        return JSONResponse({"int": num})

    res = client.get("/int/12")
    assert res.status_code == 200
    assert res.json() == {"int": 12}
