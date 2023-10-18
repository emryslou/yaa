import os, pytest

from yaa.applications import Yaa
from yaa.middlewares import BaseHttpMiddleware
from yaa.plugins.template import get_templates, Jinja2Template
from yaa.plugins.template.responses import TemplateResponse
from yaa.requests import Request
from yaa.responses import Response
from yaa.routing import Route


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


def test_templates(tmpdir, client_factory):
    path = os.path.join(tmpdir, "index.html")
    with open(path, "w") as f:
        f.write("<h1>Hello</h1>" "<a href=\"{{url_for('homepage')}}\">Template</a>")

    app = Yaa(plugins={"template": {"directory": tmpdir}})

    @app.route("/")
    async def homepage(req):
        return get_templates().response("index.html", request=req)

    client = client_factory(app)
    res = client.get("/")
    assert res.text == '<h1>Hello</h1><a href="http://testserver/">Template</a>'


def test_template_with_middleware(tmpdir, client_factory):
    path = os.path.join(tmpdir, "index.html")
    with open(path, "w") as file:
        file.write("<html>Hello, <a href='{{ url_for('homepage') }}'>world</a></html>")

    async def homepage(request):
        return get_templates().response("index.html", request=request, context={})

    class CustomMiddleware(BaseHttpMiddleware):
        async def dispatch(self, request, call_next):
            return await call_next(request)

    app = Yaa(
        debug=True,
        routes=[Route("/", endpoint=homepage)],
        middlewares=[(CustomMiddleware, {})],
        plugins={"template": {"directory": tmpdir}},
    )

    client = client_factory(app)
    response = client.get("/")
    assert response.text == "<html>Hello, <a href='http://testserver/'>world</a></html>"
    assert response.template.name == "index.html"
