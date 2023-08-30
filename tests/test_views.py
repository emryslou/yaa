import pytest

from yast.request import Request
from yast.response import PlainTextResponse
from yast.routing import Router, Path
from yast.testclient import TestClient
from yast.views import View


class HomePage(View):
    async def get(self, req: Request, username: str =None):
        if username is None:
            return PlainTextResponse('Hello, all of you')
        else:
            return PlainTextResponse(f'Hello, {username}')


app = Router(routes=[
    Path('/', HomePage),
    Path('/{username}', HomePage),
])
client = TestClient(app)

def test_view_route():
    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'Hello, all of you'

    res = client.get('/abc')
    assert res.status_code == 200
    assert res.text == 'Hello, abc'

    res = client.post('/abc')
    assert res.status_code == 405
    assert res.text == 'Method Not Allowed'
