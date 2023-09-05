import os
import pytest

from yast import TestClient
from yast.responses import Response, JSONResponse
from yast.routing import Router, Path, PathPrefix, ProtocalRouter
from yast.staticfiles import StaticFiles
from yast.websockets import WebSocket, WebSocketDisconnect


def home(scope):
    return Response('Hello Home', media_type='text/plain')

def user(scope):
    content = scope['kwargs'].get('username', None)
    if content is None:
        content = 'All Users'
    else:
        content = 'User %s' % content
    return Response(content, media_type='text/plain')


def staticfiles(scope):
    return Response('xxxx', media_type='image/ping')


def http_endpoint(scope):
    return Response('Hello, Http', media_type='text/plain')

def websocket_endpoint(scope):
    async def asgi(receive, send):
        session = WebSocket(scope, receive, send)
        await session.accept()
        await session.send_json({"hello": "websocket"})
        await session.close()
    
    return asgi

def test_routing_not_found():
    
    app = Router()
    client = TestClient(app)

    res = client.get('/')
    assert res.status_code == 404
    assert res.text == 'Not Found'


def test_routing_path():
    app = Router([
        Path('/', app=home, methods=['GET']),
        Path('/index', app=home, methods=['GET']),
    ])
    client = TestClient(app)

    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'Hello Home'
    res = client.get('/index')
    assert res.status_code == 200
    assert res.text == 'Hello Home'

    res = client.post('/')
    assert res.status_code == 405
    assert res.text == 'Method Not Allowed'

    res = client.get('/nope')
    assert res.status_code == 404
    assert res.text == 'Not Found'

def test_routing_pathprefix():
    app = Router([
        PathPrefix(
            '/user',
            app=Router([
                Path('', app=user),
                Path('/{username}', app=user),
            ]),
            methods=['GET']
        ),
        PathPrefix('/static', app=staticfiles, methods=['GET'])
    ])
    client = TestClient(app)

    res = client.get('/user')
    assert res.text == 'All Users'

    res = client.get('/user/aaaa')
    assert res.text == 'User aaaa'

    res = client.post('/static/123')
    assert res.status_code == 405
    assert res.text == 'Method Not Allowed'


def test_demo(tmpdir):
    ex_file = os.path.join(tmpdir, 'ex_file.txt')

    with open(ex_file, 'wb') as file:
        file.write(b'<ex_file content>')
    
    app = Router([
        Path('/', app=home, methods=['GET']),
        PathPrefix(
            '/user',
            app=Router([
                Path('', app=user),
                Path('/{username}', app=user),
            ]),
            methods=['GET']
        ),
        PathPrefix('/static', app=StaticFiles(directory=tmpdir), methods=['GET'])
    ])
    client = TestClient(app)

    res = client.get('/static/ex_file.txt')
    assert res.status_code == 200
    assert res.text == '<ex_file content>'

    res = client.get('/')
    assert res.status_code == 200
    assert res.content == b'Hello Home'


def test_protocal_switch():
    mixed_protocal_app = ProtocalRouter({
        'http': Router([Path('/', app=http_endpoint)]),
        'websocket': Router([Path('/', app=websocket_endpoint)]),
    })

    client = TestClient(mixed_protocal_app)
    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'Hello, Http'

    with client.wsconnect('/') as session:
        assert session.receive_json() == {"hello": 'websocket'}
    
    with pytest.raises(WebSocketDisconnect):
        client.wsconnect('/404')


def test_router():
    from yast import Yast
    app = Yast()

    @app.route('/func')
    def func_homepage(_):
        return Response('Hello Func HomePage', media_type='text/plain')
    
    @app.ws_route('/ws')
    async def ws_endpoint(ss):
        await ss.accept()
        await ss.send_text('Hello, Ws')
        await ss.close()
    
    client = TestClient(app)
    res = client.get('/func')
    assert res.status_code == 200
    assert res.text == 'Hello Func HomePage'

    with client.wsconnect('/ws') as ss:
        text = ss.receive_text()
        assert text == 'Hello, Ws'
    