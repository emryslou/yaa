import pytest

from yaa.plugins.template.responses import TemplateResponse
from yaa.requests import Request
from yaa.responses import Response


def test_template_response(client_factory):
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

    client = client_factory(app)
    res = client.get("/")
    assert res.text == "username: eml"
    assert res.template.name == "index.html"
    assert res.context["username"] == "eml"


def test_template_require_request():
    with pytest.raises(ValueError):
        TemplateResponse(None, {})


def test_template_jinja2_response(tmpdir, client_factory):
    import os
    from yaa.applications import Yaa

    path = os.path.join(tmpdir, "tpl.example.1.html")
    with open(path, "w") as tpl:
        tpl.write('<html>{{hello}}{{url_for("home")}}</html>')

    app = Yaa(plugins={"template": {"directory": tmpdir}})
    from yaa.plugins.template import get_templates

    @app.route("/")
    def home(req: Request):
        return get_templates().response(
            "tpl.example.1.html",
            request=req,
            context={"hello": req.query_params["hello"]},
        )

    client = client_factory(app)
    res = client.get("/?hello=abcd1234")
    assert res.template.name == "tpl.example.1.html"
    assert res.status_code == 200
    assert res.text == "<html>abcd1234http://testserver/</html>"


def test_calls_context_processors(tmp_path, client_factory):
    from yaa.applications import Yaa
    from yaa.plugins.template import Jinja2Template, get_templates
    from yaa.routing import Route

    path = tmp_path / "index.html"
    path.write_text("<html>Hello {{ username }}</html>")

    async def homepage(request):
        return get_templates().response("index.html", request=request, context={})

    def hello_world_processor(request):
        return {"username": "World"}

    app = Yaa(
        debug=True,
        routes=[Route("/", endpoint=homepage)],
        plugins={
            "template": {
                "directory": tmp_path,
                "context_processors": [hello_world_processor],
            }
        },
    )

    client = client_factory(app)
    response = client.get("/")
    assert response.text == "<html>Hello World</html>"
    assert response.template.name == "index.html"
    assert set(response.context.keys()) == {"request", "username"}
