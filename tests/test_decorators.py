from yast import AsgiApp, Response, TestClient

def test_asgi_sync():
    @AsgiApp
    def app(request):
        return Response('hello, response', media_type='text/plain')
    
    client = TestClient(app)

    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'hello, response'

def test_asgi_async():
    @AsgiApp
    async def app(request):
        return Response('hello, response', media_type='text/plain')
    
    client = TestClient(app)

    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'hello, response'

def test_asgi_async_body():
    @AsgiApp
    async def app(request):
        body = await request.body()
        return Response('hello, response:' + body.decode(), media_type='text/plain')
    
    client = TestClient(app)

    res = client.post('/', data='111')
    assert res.status_code == 200
    assert res.text == 'hello, response:111'