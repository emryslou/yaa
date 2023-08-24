from yast import TestClient, Request, JSONResponse

def test_request_url():
    
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            data = {'method': request.method, 'url': request.url}
            response = JSONResponse(data)
            await response(recv, send)

        return asgi
    
    client = TestClient(app)
    res = client.get('/path/to/page?a=abc')
    assert res.json() == {'method': 'GET', 'url': 'http://testserver/path/to/page?a=abc'}


def test_request_query_params():
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            data = {'params': dict(request.query_params)}
            response = JSONResponse(data)
            await response(recv, send)

        return asgi
    
    client = TestClient(app)
    res = client.get('/path/to/page?a=abc')
    assert res.json() == {'params': {'a': 'abc'}}


def test_request_headers():
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            data = {'headers': dict(request.headers)}
            response = JSONResponse(data)
            await response(recv, send)

        return asgi
    
    client = TestClient(app)
    res = client.get('/path/to/page?a=abc', headers={'host': 'abc.com'})
    assert res.json() == {
        'headers': {
            'user-agent': 'testclient',
            'host': 'abc.com',
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate',
            'connection': 'keep-alive'
        }
    }


def test_request_body():
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            body = await request.body()
            response = JSONResponse({'body': body.decode()})
            await response(recv, send)

        return asgi
    
    client = TestClient(app)
    res = client.get('/')
    assert res.json() == {'body':''}

    res = client.post('/', json={'a': '123'})
    assert res.json() == {'body':'{"a": "123"}'}

    res = client.post('/', data="aaa")
    assert res.json() == {'body':'aaa'}


def test_request_json():
    def app(scope):
        async def asgi(recv, send):
            request = Request(scope, recv)
            body = await request.json()
            response = JSONResponse({'json': body})
            await response(recv, send)

        return asgi
    
    client = TestClient(app)

    res = client.post('/', json={'a': '123'})
    assert res.json() == {'json':{"a": "123"}}