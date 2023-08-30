import pytest

from yast import App, TestClient
from yast.views import View
from yast.request import Request
from yast.response import PlainTextResponse

app = App()

@app.route('/')
@app.route('/{username}')
class HomePage(View):
    async def get(self, req: Request, username: str =None):
        if username is None:
            return PlainTextResponse('Hello, all of you')
        else:
            return PlainTextResponse(f'Hello, {username}')


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