from yast import TestClient
from yast.formparsers import FormParser, UploadFile
from yast.requests import Request
from yast.responses import Response

class ForceMultipartDict(dict):
    def __bool__(self):
        return True


FORCE_MULTIPART = ForceMultipartDict()


def app(scope):
    async def asgi(receive, sedd):
        req = Request(scope, receive)
        data = await req.form()
        output = {}
        for k, v in data.items():
            if isinstance(v, UploadFile):
                content = await v.read()
                output[key] = {
                        'filename': v.filename, 'content': content.decode()
                    }
            else:
                output[k] = v
        await req.close()

        res = Response(output)
        await res(receive, send)

    return asgi

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
