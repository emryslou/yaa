import os
import pytest
from yast import TestClient
from yast import StaticFiles, StaticFile


def test_staticfile(tmpdir):
    path = os.path.join(tmpdir, "example.txt")
    with open(path, 'w') as file:
        file.write('<file content>')
    
    app = StaticFile(path=path)

    client = TestClient(app)
    res = client.get('/')
    assert res.status_code == 200
    assert res.text == '<file content>'

    res = client.post('/')
    assert res.status_code == 406
    assert res.text == 'Method not allowed'


def test_staticfile_with_directory_raise_error(tmpdir):
    app = StaticFile(path=tmpdir)

    client = TestClient(app)
    
    with pytest.raises(RuntimeError) as exc:
        res = client.get('/')
    
    assert 'is not a file' in str(exc)


    app = StaticFile(path=os.path.join(tmpdir, '404.txt'))

    client = TestClient(app)
    
    with pytest.raises(RuntimeError) as exc:
        res = client.get('/')
    
    assert 'does not found' in str(exc)


def test_staticfiles(tmpdir):
    path = os.path.join(tmpdir, "example.txt")
    with open(path, 'w') as file:
        file.write('<file content>')
    
    app = StaticFiles(directory=tmpdir)

    client = TestClient(app)

    res = client.get('/example.txt')
    assert res.status_code == 200
    assert res.text == '<file content>'


    res = client.post('/example.txt')
    assert res.status_code == 406
    assert res.text == 'Method not allowed'


    res = client.get('/')
    assert res.status_code == 404
    assert res.text == 'Not found'


    res = client.get('/404.txt')
    assert res.status_code == 404
    assert res.text == 'Not found'



if __name__ == '__main__':
    test_staticfiles('.')