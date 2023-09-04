from yast import TestClient
from yast.formparsers import FormParser, UploadFile
from yast.requests import Request
from yast.responses import Response, JSONResponse

class ForceMultipartDict(dict):
    def __bool__(self):
        return True


FORCE_MULTIPART = ForceMultipartDict()


def app(scope):
    async def asgi(receive, send):
        req = Request(scope, receive)
        data = await req.form()
        output = {}
        for k, v in data.items():
            if isinstance(v, UploadFile):
                content = await v.read()
                print('debug -- 09', content)
                output[k] = {
                        'filename': v.filename, 'content': content.decode()
                    }
            else:
                output[k] = v
        await req.close()
        print('debug -- 11', output)
        res = JSONResponse(output)
        await res(receive, send)

    return asgi

def test_formparsers_multipart_request_data(tmpdir):
    client = TestClient(app)
    res = client.get('/', data={'some': 'data'}, files=FORCE_MULTIPART)
    assert res.json() == {
        'some': 'data'
    }

def test_formparsers_multipart_request_files(tmpdir):
    import os
    path = os.path.join(tmpdir, 'test.txt')
    with open(path, 'wb') as f:
        f.write(b'<file content>')
    
    client = TestClient(app)
    res = client.get('/', files={'test': open(path, 'rb')})
    assert res.json() == {
        'test': {
            'filename': 'test.txt',
            'content': '<file content>',
        }
    }


def test_urlencoded_request_data(tmpdir):
    client = TestClient(app)
    response = client.post("/", data={"some": "data"})
    assert response.json() == {"some": "data"}

def test_no_request_data(tmpdir):
    client = TestClient(app)
    response = client.post("/")
    assert response.json() == {}