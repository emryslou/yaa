import asyncio

import pytest

from yaa import TestClient
from yaa.requests import ClientDisconnect, Request
from yaa.responses import JSONResponse


class ForceMultipartDict(dict):
    def __bool__(self):
        return True


FORCE_MULTIPART = ForceMultipartDict()


def test_request_url():
    """test"""

    async def app(scope, recv, send):
        request = Request(scope, recv)
        data = {"method": request.method, "url": str(request.url)}
        response = JSONResponse(data)
        await response(scope, recv, send)

    client = TestClient(app)
    res = client.get("/path/to/page?a=abc")
    assert res.json() == {
        "method": "GET",
        "url": "http://testserver/path/to/page?a=abc",
    }


def test_request_query_params():
    async def app(scope, recv, send):
        request = Request(scope, recv)
        data = {"params": dict(request.query_params)}
        response = JSONResponse(data)
        await response(scope, recv, send)

    client = TestClient(app)
    res = client.get("/path/to/page?a=abc")
    assert res.json() == {"params": {"a": "abc"}}


def test_request_headers():
    async def app(scope, recv, send):
        request = Request(scope, recv)
        response = JSONResponse({"headers": dict(request.headers)})
        await response(scope, recv, send)

    client = TestClient(app)
    res = client.get("/path/to/page?a=abc", headers={"host": "abc.com"})
    assert res.json() == {
        "headers": {
            "user-agent": "testclient",
            "host": "abc.com",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate",
            "connection": "keep-alive",
        }
    }


def test_request_body():
    async def app(scope, recv, send):
        request = Request(scope, recv)
        body = await request.body()
        response = JSONResponse({"body": body.decode()})
        await response(scope, recv, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.json() == {"body": ""}

    res = client.post("/", json={"a": "123"})
    assert res.json() == {"body": '{"a": "123"}'}

    res = client.post("/", data="aaa")
    assert res.json() == {"body": "aaa"}


def test_request_json():
    async def app(scope, recv, send):
        request = Request(scope, recv)
        body = await request.json()
        response = JSONResponse({"json": body})
        await response(scope, recv, send)

    client = TestClient(app)

    res = client.post("/", json={"a": "123"})
    assert res.json() == {"json": {"a": "123"}}


def test_request_stream():
    async def app(scope, recv, send):
        request = Request(scope, recv)
        body = b""
        async for chunk in request.stream():
            body += chunk
        response = JSONResponse({"body": body.decode()})
        await response(scope, recv, send)

    client = TestClient(app)
    res = client.get("/")
    assert res.json() == {"body": ""}

    res = client.post("/", json={"a": "123"})
    assert res.json() == {"body": '{"a": "123"}'}

    res = client.post("/", data="1234")
    assert res.json() == {"body": "1234"}


def test_request_body_then_stream():
    async def app(scope, recv, send):
        request = Request(scope, recv)

        body = await request.body()

        chunks = b""
        async for chunk in request.stream():
            chunks += chunk
        response = JSONResponse({"body": body.decode(), "stream": chunks.decode()})
        await response(scope, recv, send)

    client = TestClient(app)
    res = client.post("/", data="1234")
    assert res.json() == {"body": "1234", "stream": "1234"}


def test_request_body_then_stream_err():
    """ """

    async def app(scope, recv, send):
        request = Request(scope, recv)
        chunks = b""
        async for chunk in request.stream():
            chunks += chunk
        try:
            body = await request.body()
        except RuntimeError:
            body = b"<stream consumed>"
        response = JSONResponse({"body": body.decode(), "stream": chunks.decode()})
        await response(scope, recv, send)

    client = TestClient(app)
    res = client.post("/", data="1234")
    assert res.json() == {"body": "<stream consumed>", "stream": "1234"}


def test_quest_relative_url():
    async def app(scope, recv, send):
        req = Request(scope, recv)
        data = {"method": req.method, "relative_url": req.relative_url}
        res = JSONResponse(data)
        await res(scope, recv, send)

    client = TestClient(app)

    res = client.get("/123?a=abc")
    assert res.json() == {"method": "GET", "relative_url": "/123?a=abc"}

    res = client.get("https://exmaple.org:123/")
    assert res.json() == {"method": "GET", "relative_url": "/"}


def test_request_disconnect():
    async def app(scope, recv, send):
        req = Request(scope, recv)
        await req.body()

    async def recv(*args, **kwargs):
        return {"type": "http.disconnect"}

    scope = {"method": "POST", "path": "/"}

    loop = asyncio.get_event_loop()
    with pytest.raises(ClientDisconnect):
        loop.run_until_complete(app(scope, recv, None))


def test_chunked_encoding():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        body = await request.body()
        response = JSONResponse({"body": body.decode()})
        await response(scope, receive, send)

    client = TestClient(app)

    def post_body():
        yield b"foo"
        yield "bar"

    response = client.post("/", data=post_body())
    assert response.json() == {"body": "foobar"}


def test_request_client():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        response = JSONResponse(
            {"host": request.client.host, "port": request.client.port}
        )
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/")
    assert response.json() == {"host": "testclient", "port": 50000}


async def app_read_body(scope, receive, send):
    request = Request(scope, receive)
    # Read bytes, to force request.stream() to return the already parsed body
    body_bytes = await request.body()
    data = await request.form()
    output = {}
    for key, value in data.items():
        output[key] = value
    await request.close()
    response = JSONResponse(output)
    await response(scope, receive, send)


def test_urlencoded_multi_field_app_reads_body(tmpdir):
    client = TestClient(app_read_body)
    response = client.post("/", data={"some": "data", "second": "key pair"})
    assert response.json() == {"some": "data", "second": "key pair"}


def test_multipart_multi_field_app_reads_body(tmpdir):
    client = TestClient(app_read_body)
    response = client.post(
        "/", data={"some": "data", "second": "key pair"}, files=FORCE_MULTIPART
    )
    assert response.json() == {"some": "data", "second": "key pair"}


def test_request_is_disconnected():
    """
    If a client disconnect occurs while reading request body
    then ClientDisconnect should be raised.
    """
    disconnected_after_response = None

    async def app(scope, receive, send):
        nonlocal disconnected_after_response
        request = Request(scope, receive)
        await request.body()
        disconnected = await request.is_disconnected()
        response = JSONResponse({"disconnected": disconnected})
        await response(scope, receive, send)
        disconnected_after_response = await request.is_disconnected()

    client = TestClient(app)
    response = client.get("/")
    assert response.json() == {"disconnected": False}
    assert disconnected_after_response


def test_request_state():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        request.state.example = "abc"
        response = JSONResponse({"state.example": request.state.example})
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/123?a=abc")
    assert response.json() == {"state.example": "abc"}


def test_state():
    from yaa.requests import State

    s = State({"aa": "cc"})

    assert s.aa == "cc"

    s.bb = "xx"

    assert s.bb == "xx"

    delattr(s, "bb")

    with pytest.raises(AttributeError):
        _ = s.bb

    s._state["cc"] = "cc"

    assert s.cc == "cc"


def test_request_send_push_promise():
    async def app(scope, receive, send):
        # the server is push-enabled
        scope["extensions"]["http.response.push"] = {}
        request = Request(scope, receive, send)
        await request.send_push_promise("/style.css")
        response = JSONResponse({"json": "OK"})
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/")
    assert response.json() == {"json": "OK"}


def test_request_send_push_promise_without_push_extension():
    """
    If server does not support the `http.response.push` extension,
    .send_push_promise() does nothing.
    """

    async def app(scope, receive, send):
        request = Request(scope)
        await request.send_push_promise("/style.css")
        response = JSONResponse({"json": "OK"})
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/")
    assert response.json() == {"json": "OK"}


def test_request_send_push_promise_without_setting_send():
    """
    If Request is instantiated without the send channel, then
    .send_push_promise() is not available.
    """

    async def app(scope, receive, send):
        # the server is push-enabled
        scope["extensions"]["http.response.push"] = {}
        data = "OK"
        request = Request(scope)
        try:
            await request.send_push_promise("/style.css")
        except RuntimeError:
            data = "Send channel not available"
        response = JSONResponse({"json": data})
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/")
    assert response.json() == {"json": "Send channel not available"}


def test_cookie_lenient_parsing():
    """
    The following test is based on a cookie set by Okta, a well-known authorization service.
    It turns out that it's common practice to set cookies that would be invalid according to
    the spec.
    """
    tough_cookie = (
        "provider-oauth-nonce=validAsciiblabla; "
        'okta-oauth-redirect-params={"responseType":"code","state":"somestate",'
        '"nonce":"somenonce","scopes":["openid","profile","email","phone"],'
        '"urls":{"issuer":"https://subdomain.okta.com/oauth2/authServer",'
        '"authorizeUrl":"https://subdomain.okta.com/oauth2/authServer/v1/authorize",'
        '"userinfoUrl":"https://subdomain.okta.com/oauth2/authServer/v1/userinfo"}}; '
        "importantCookie=importantValue; sessionCookie=importantSessionValue"
    )
    expected_keys = {
        "importantCookie",
        "okta-oauth-redirect-params",
        "provider-oauth-nonce",
        "sessionCookie",
    }

    async def app(scope, receive, send):
        request = Request(scope, receive)
        response = JSONResponse({"cookies": request.cookies})
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/", headers={"cookie": tough_cookie})
    result = response.json()
    assert len(result["cookies"]) == 4
    assert set(result["cookies"].keys()) == expected_keys


# These test cases copied from Tornado's implementation


@pytest.mark.parametrize(
    "set_cookie,expected",
    [
        ("chips=ahoy; vienna=finger", {"chips": "ahoy", "vienna": "finger"}),
        # all semicolons are delimiters, even within quotes
        (
            'keebler="E=mc2; L=\\"Loves\\"; fudge=\\012;"',
            {"keebler": '"E=mc2', "L": '\\"Loves\\"', "fudge": "\\012", "": '"'},
        ),
        # Illegal cookies that have an '=' char in an unquoted value.
        ("keebler=E=mc2", {"keebler": "E=mc2"}),
        # Cookies with ':' character in their name.
        ("key:term=value:term", {"key:term": "value:term"}),
        # Cookies with '[' and ']'.
        ("a=b; c=[; d=r; f=h", {"a": "b", "c": "[", "d": "r", "f": "h"}),
        # Cookies that RFC6265 allows.
        ("a=b; Domain=example.com", {"a": "b", "Domain": "example.com"}),
        # parse_cookie() keeps only the last cookie with the same name.
        ("a=b; h=i; a=c", {"a": "c", "h": "i"}),
    ],
)
def test_cookies_edge_cases(set_cookie, expected):
    async def app(scope, receive, send):
        request = Request(scope, receive)
        response = JSONResponse({"cookies": request.cookies})
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/", headers={"cookie": set_cookie})
    result = response.json()
    assert result["cookies"] == expected


@pytest.mark.parametrize(
    "set_cookie,expected",
    [
        # Chunks without an equals sign appear as unnamed values per
        # https://bugzilla.mozilla.org/show_bug.cgi?id=169091
        (
            "abc=def; unnamed; django_language=en",
            {"": "unnamed", "abc": "def", "django_language": "en"},
        ),
        # Even a double quote may be an unamed value.
        ('a=b; "; c=d', {"a": "b", "": '"', "c": "d"}),
        # Spaces in names and values, and an equals sign in values.
        ("a b c=d e = f; gh=i", {"a b c": "d e = f", "gh": "i"}),
        # More characters the spec forbids.
        ('a   b,c<>@:/[]?{}=d  "  =e,f g', {"a   b,c<>@:/[]?{}": 'd  "  =e,f g'}),
        # Unicode characters. The spec only allows ASCII.
        # ("saint=André Bessette", {"saint": "André Bessette"}),
        # Browsers don't send extra whitespace or semicolons in Cookie headers,
        # but cookie_parser() should parse whitespace the same way
        # document.cookie parses whitespace.
        # ("  =  b  ;  ;  =  ;   c  =  ;  ", {"": "b", "c": ""}),
    ],
)
def test_cookies_invalid(set_cookie, expected):
    """
    Cookie strings that are against the RFC6265 spec but which browsers will send if set
    via document.cookie.
    """

    async def app(scope, receive, send):
        request = Request(scope, receive)
        response = JSONResponse({"cookies": request.cookies})
        await response(scope, receive, send)

    client = TestClient(app)
    response = client.get("/", headers={"cookie": set_cookie})
    result = response.json()
    assert result["cookies"] == expected
