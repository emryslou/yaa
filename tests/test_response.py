import pytest
from yast import Response, StreamingResponse, TestClient

def test_response_text():
    def app(scope):
        async def asgi(recv, send):
            response = Response('Hello, Response', media_type='text/plain')
            await response(recv, send)

        return asgi
    
    client = TestClient(app)
    res = client.get('/')
    assert res.text == 'Hello, Response'

def test_response_bytes():
    def app(scope):
        async def asgi(recv, send):
            response = Response(b'image/png', media_type='image/png')
            await response(recv, send)

        return asgi
    
    client = TestClient(app)
    res = client.get('/')
    assert res.content == b'image/png'

def test_response_streaming():
    import asyncio
    def app(scope):
        async def numbers(minimum, maximum):
            for i in range(minimum, maximum + 1):
                yield str(i)
                if i != maximum:
                    yield ", "
                await asyncio.sleep(0)

        async def asgi(receive, send):
            generator = numbers(1, 5)
            response = StreamingResponse(generator, media_type="text/plain")
            await response(receive, send)

        return asgi

    client = TestClient(app)
    response = client.get("/")
    assert response.text == "1, 2, 3, 4, 5"


def test_response_headers():
    def app(scope):
        async def asgi(recv, send):
            headers = {'x-header-1': '123', 'x-header-2': '234'}
            response = Response('Hello, Response', media_type='text/plain', headers=headers)
            await response(recv, send)

        return asgi
    
    client = TestClient(app)
    res = client.get('/')
    assert res.headers['x-header-1'] == '123'
    assert res.headers['x-header-2'] == '234'
