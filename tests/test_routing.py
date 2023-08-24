from yast import TestClient, Response, JSONResponse, Router, Path, PathPrefix

def home(scope):
    return Response('Hello Home', media_type='text/plain')

def user(scope):
    content = scope['kwargs'].get('username', None)
    if content is None:
        content = 'All Users'
    else:
        content = 'User %s' % content
    return Response(content, media_type='text/plain')


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
    ])
    client = TestClient(app)

    res = client.get('/user')
    assert res.text == 'All Users'

    res = client.get('/user/aaaa')
    assert res.text == 'User aaaa'

if __name__ == '__main__':
    test_routing_pathprefix() 