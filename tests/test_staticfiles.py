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

    res = client.get('/../../../example.txt')
    assert res.status_code == 200
    assert res.text == '<file content>'

def test_staticfiles_config_check_occurs_only_once(tmpdir):
    app = StaticFiles(directory=tmpdir)
    client = TestClient(app)
    assert not app.config_checked
    response = client.get("/")
    assert app.config_checked
    response = client.get("/")
    assert app.config_checked

def test_staticfiles_prevents_breaking_out_of_directory(tmpdir):
    directory = os.path.join(tmpdir, 'foo')
    os.mkdir(directory)

    path = os.path.join(tmpdir, "example.txt")
    with open(path, "w") as file:
        file.write("outside root dir")

    app = StaticFiles(directory=directory)
    # We can't test this with 'requests', so we call the app directly here.
    response = app({'method': 'GET', 'path': '/../example.txt'})
    assert response.status_code == 404
    assert response.body == b"Not found"


def test_staticfile_largefile(tmpdir):
    path = os.path.join(tmpdir, "example.txt")
    content = "this is a lot of content" * 200
    print("content len = ", len(content))
    with open(path, "w") as file:
        file.write(content)
    app = StaticFile(path=path)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert len(content) == len(response.text)
    assert content == response.text


if __name__ == '__main__':
    test_staticfiles('.')