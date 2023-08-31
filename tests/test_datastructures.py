from yast.datastructures import URL, QueryParams, Headers

def test_url():
    url = URL('http://user:passwd@www.baidu.com:443/abcd/test.php?aaa=ccc#fff')
    assert url == 'http://user:passwd@www.baidu.com:443/abcd/test.php?aaa=ccc#fff'
    assert url.scheme == 'http'
    assert url.netloc == 'user:passwd@www.baidu.com:443'
    assert url.path == '/abcd/test.php'
    assert url.params == ''
    assert url.fragment == 'fff'
    assert url.query == 'aaa=ccc'
    assert url.port == 443
    assert url.username == 'user'
    assert url.password == 'passwd'
    assert url.hostname == 'www.baidu.com'

    _new = url.replace(scheme='ws', path='/replace/a/path')
    assert _new.scheme == 'ws'
    assert str(_new).startswith('ws://')
    assert str(_new).__contains__('/replace/a/path')
    assert not str(_new).__contains__('/abcd/test.php')

    # username:passwd discard ????
    _new = url.replace(port=None)
    assert _new == 'http://www.baidu.com/abcd/test.php?aaa=ccc#fff'


def test_query_params():
    qry_prm = QueryParams([("a", "123"), ("a", "456"), ("bb", "xxx")])
    assert "a" in qry_prm
    assert "A" not in qry_prm
    assert qry_prm['a'] == '123'
    assert qry_prm.get('a') == '123'
    assert qry_prm.get('??', default=None) == None
    assert qry_prm.getlist('a') == ['123', '456']
    assert QueryParams() == {}


def test_headers():
    h = Headers([(b"a", b"123"), (b"a", b"456"), (b"b", b"789")])
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
    assert list(h) == [("a", "123"), ("a", "456"), ("b", "789")]
    assert dict(h) == {"a": "123", "b": "789"}
    assert repr(h) == "Headers([('a', '123'), ('a', '456'), ('b', '789')])"
    assert h == Headers([(b"a", b"123"), (b"b", b"789"), (b"a", b"456")])
    assert h != [(b"a", b"123"), (b"A", b"456"), (b"b", b"789")]
    h = Headers()
    assert not h.items()

def test_headers_mutablecopy():
    h = Headers([(b"a", b"123"), (b"a", b"456"), (b"b", b"789")])
    c = h.mutablecopy()
    assert c.items() == [("a", "123"), ("a", "456"), ("b", "789")]
    c["a"] = "abc"
    assert c.items() == [("a", "abc"), ("b", "789")]
