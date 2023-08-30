import os
import pytest

from yast import TestClient, Response, JSONResponse, StaticFiles
from yast.routing import Router, Path, PathPrefix, ProtocalRouter
from yast.websockets import WebSocketSession, WebSocketDisconnect


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
    async def asgi(recevie, send):
        session = WebSocketSession(scope, recevie, send)
        await session.accept()
        await session.send_json({"hello": "websocket"})
        await session.close()
    
    return asgi

def test_routing_not_found():
    
    app = Router()
    client = TestClient(app)

    res = client.get('/')
    assert res.status_code == 404
    assert res.text == 'Not found'


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
    assert res.status_code == 406
    assert res.text == 'Method not allowed'

    res = client.get('/nope')
    assert res.status_code == 404
    assert res.text == 'Not found'

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
    assert res.status_code == 406
    assert res.text == 'Method not allowed'


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
        assert session.recevie_json() == {"hello": 'websocket'}
    
    with pytest.raises(WebSocketDisconnect):
        client.wsconnect('/404')
