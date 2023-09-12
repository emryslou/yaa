from yast.datastructures import URL, Headers, QueryParams


def test_url():
    url = URL("http://user:passwd@www.baidu.com:443/abcd/test.php?aaa=ccc#fff")
    assert url == "http://user:passwd@www.baidu.com:443/abcd/test.php?aaa=ccc#fff"
    assert url.scheme == "http"
    assert url.netloc == "user:passwd@www.baidu.com:443"
    assert url.path == "/abcd/test.php"
    assert url.params == ""
    assert url.fragment == "fff"
    assert url.query == "aaa=ccc"
    assert url.port == 443
    assert url.username == "user"
    assert url.password == "passwd"
    assert url.hostname == "www.baidu.com"

    _new = url.replace(scheme="ws", path="/replace/a/path")
    assert _new.scheme == "ws"
    assert str(_new).startswith("ws://")
    assert str(_new).__contains__("/replace/a/path")
    assert not str(_new).__contains__("/abcd/test.php")

    # username:passwd discard ????
    _new = url.replace(port=None)
    assert _new == "http://www.baidu.com/abcd/test.php?aaa=ccc#fff"


def test_query_params():
    q = QueryParams(query_string="a=123&a=456&b=789")
    assert "a" in q
    assert "A" not in q
    assert "c" not in q
    assert q["a"] == "123"
    assert q.get("a") == "123"
    assert q.get("nope", default=None) is None
    assert q.getlist("a") == ["123", "456"]
    assert q.keys() == ["a", "a", "b"]
    assert q.values() == ["123", "456", "789"]
    assert q.items() == [("a", "123"), ("a", "456"), ("b", "789")]
    assert list(q) == ["a", "a", "b"]
    assert dict(q) == {"a": "123", "b": "789"}
    assert str(q) == "a=123&a=456&b=789"
    assert repr(q) == "QueryParams(query_string='a=123&a=456&b=789')"
    assert QueryParams({"a": "123", "b": "456"}) == QueryParams(
        query_string="a=123&b=456"
    )
    assert QueryParams({"a": "123", "b": "456"}) != {"b": "456", "a": "123"}
    assert QueryParams({"a": "123", "b": "456"}) == QueryParams(
        {"b": "456", "a": "123"}
    )
    assert QueryParams() == QueryParams({})


def test_headers():
    h = Headers(raw=[(b"a", b"123"), (b"a", b"456"), (b"b", b"789")])
    assert "a" in h
    assert "A" in h
    assert "b" in h
    assert "B" in h
    assert "c" not in h
    assert h["a"] == "123"
    assert h.get("a") == "123"
    assert h.get("nope", default=None) is None
    assert h.getlist("a") == ["123", "456"]
    assert h.keys() == ["a", "a", "b"]
    assert h.values() == ["123", "456", "789"]
    assert h.items() == [("a", "123"), ("a", "456"), ("b", "789")]
    assert list(h) == ["a", "a", "b"]
    assert dict(h) == {"a": "123", "b": "789"}
    assert repr(h) == "Headers(raw=[(b'a', b'123'), (b'a', b'456'), (b'b', b'789')])"
    assert h == Headers(raw=[(b"a", b"123"), (b"b", b"789"), (b"a", b"456")])
    assert h != [(b"a", b"123"), (b"A", b"456"), (b"b", b"789")]
    h = Headers()
    assert not h.items()


def test_headers_mutablecopy():
    h = Headers(raw=[(b"a", b"123"), (b"a", b"456"), (b"b", b"789")])
    c = h.mutablecopy()
    assert c.items() == [("a", "123"), ("a", "456"), ("b", "789")]
    c["a"] = "abc"
    assert c.items() == [("a", "abc"), ("b", "789")]


def test_url_from_scope():
    u = URL(
        scope={
            "path": "/a/path/to/somewhere",
            "query_string": b"abc=123",
            "headers": [],
        }
    )
    assert u == "/a/path/to/somewhere?abc=123"

    url = URL(
        scope={
            "scheme": "https",
            "server": ("example.org", 443),
            "path": "/path/to/a/path",
            "query_string": b"abc=123",
            "headers": [],
        }
    )

    assert url == "https://example.org/path/to/a/path?abc=123"
    assert repr(url) == "URL('https://example.org/path/to/a/path?abc=123')"
