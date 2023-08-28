from yast import TestClient, Response, JSONResponse, StaticFiles
from yast.routing import Router, Path, PathPrefix

import os

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
    