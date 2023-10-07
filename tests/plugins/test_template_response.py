import pytest

from yaa.plugins.template.responses import TemplateResponse
from yaa.requests import Request
from yaa.responses import Response
from yaa.testclient import TestClient


def test_template_response():
    class Template:
        def __init__(self, name):
            self.name = name

        def render(self, context):
            return f"username: {context['username']}"

    async def app(scope, receive, send):
        req = Request(scope=scope)

        template = Template("index.html")
        context = {"username": "eml", "request": req}

        res = TemplateResponse(template=template, context=context)
        await res(scope, receive, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.text == "username: eml"
    assert res.template.name == "index.html"
    assert res.context["username"] == "eml"


def test_template_require_request():
    with pytest.raises(ValueError):
        TemplateResponse(None, {})


def test_template_jinja2_response(tmpdir):
    import os
    from yaa.applications import Yaa

    path = os.path.join(tmpdir, "tpl.example.1.html")
    with open(path, "w") as tpl:
        tpl.write('<html>{{hello}}{{url_for("home")}}</html>')

    app = Yaa(plugins={"template": {"template_directory": tmpdir}})
    from yaa.plugins.template import templates

    @app.route("/")
    def home(req: Request):
        return templates.response(
            "tpl.example.1.html",
            request=req,
            context={"hello": req.query_params["hello"]},
        )

    client = TestClient(app)
    res = client.get("/?hello=abcd1234")
    assert res.template.name == "tpl.example.1.html"
    assert res.status_code == 200
    assert res.text == "<html>abcd1234http://testserver/</html>"
