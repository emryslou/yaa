import os

from yast import TestClient, Yast
from yast.responses import HTMLResponse
from yast.plugins.template import templates


def test_templates(tmpdir):
    path = os.path.join(tmpdir, "index.html")
    with open(path, "w") as f:
        f.write("<h1>Hello</h1>" "<a href=\"{{url_for('homepage')}}\">Template</a>")

    app = Yast(plugins={"template": {"template_directory": tmpdir}})

    @app.route("/")
    async def homepage(req):
        return templates.response("index.html", request=req)

    client = TestClient(app)
    res = client.get("/")
    assert res.text == '<h1>Hello</h1><a href="http://testserver/">Template</a>'
