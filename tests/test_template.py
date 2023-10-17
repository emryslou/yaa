import os

from yaa import Yaa
from yaa.responses import HTMLResponse


def test_templates(tmpdir, client_factory):
    from yaa.plugins.template import get_templates

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
