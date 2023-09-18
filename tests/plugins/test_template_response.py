import pytest

from yast.plugins.template.responses import TemplateResponse
from yast.requests import Request
from yast.responses import Response
from yast.testclient import TestClient


def test_template_response():
    def app(scope):
        req = Request(scope=scope)

        class Template:
            def __init__(self, name):
                self.name = name

            def render(self, context):
                return f"username: {context['username']}"

        async def asgi(receive, send):
            template = Template("index.html")
            context = {"username": "eml", "request": req}

            res = TemplateResponse(template=template, context=context)
            await res(receive, send)

        return asgi

    client = TestClient(app)
    res = client.get("/")
    assert res.text == "username: eml"
    assert res.template.name == "index.html"
    assert res.context["username"] == "eml"


def test_template_require_request():
    with pytest.raises(ValueError):
        TemplateResponse(None, {})
