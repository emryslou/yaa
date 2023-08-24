from yast import AsgiApp, Response, TestClient

def test_asgi_app():
    
    @AsgiApp
    def app(request):
        return Response('hello, response', media_type='text/plain')
    
    client = TestClient(app)

    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'hello, response'