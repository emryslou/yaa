from yast.datastructures.urls import *


def test_address():
    a = Address("localhost", 8088)
    assert str(a) == "Address(host='localhost', port=8088)"
    assert a.host == "localhost"
    assert a.port == 8088


def test_url():
    url = URL("http://user:passwd@www.baidu.com:443/abcd/test.php?aaa=ccc#fff")
    assert url == "http://user:passwd@www.baidu.com:443/abcd/test.php?aaa=ccc#fff"
    assert url.scheme == "http"
    assert url.netloc == "user:passwd@www.baidu.com:443"
    assert url.path == "/abcd/test.php"
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

    _new = url.replace(port=None)
    assert _new == "http://user:passwd@www.baidu.com/abcd/test.php?aaa=ccc#fff"


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


def test_hidden_passwd():
    u = URL("https://example.org/path/to/somewhere")
    assert repr(u) == "URL('https://example.org/path/to/somewhere')"
    u = URL("https://username@example.org/path/to/somewhere")
    assert repr(u) == "URL('https://username@example.org/path/to/somewhere')"
    u = URL("https://username:password@example.org/path/to/somewhere")
    assert repr(u) == "URL('https://username:********@example.org/path/to/somewhere')"


def test_query_params():
    q = QueryParams("a=123&a=456&b=789")
    assert "a" in q
    assert "A" not in q
    assert "c" not in q
    assert q["a"] == "456"
    assert q.get("a") == "456"
    assert q.get("nope", default=None) is None
    assert q.getlist("a") == ["123", "456"]
    assert list(q.keys()) == ["a", "b"]
    assert list(q.values()) == ["456", "789"]
    assert list(q.items()) == [("a", "456"), ("b", "789")]
    assert list(q) == ["a", "b"]
    assert dict(q) == {"a": "456", "b": "789"}
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


def test_database_url():
    u = DatabaseURL("postgresql://u:p@localhost:5432/mydb")
    u = u.replace(name="test")
    assert u.name == "test"
    assert str(u) == "postgresql://u:p@localhost:5432/test"


def test_csv():
    csv = CommaSeparatedStrings('"localhost", "127.0.0.1", 0.0.0.0')
    assert list(csv) == ["localhost", "127.0.0.1", "0.0.0.0"]
    assert repr(csv) == "CommaSeparatedStrings(['localhost', '127.0.0.1', '0.0.0.0'])"
    assert str(csv) == "'localhost', '127.0.0.1', '0.0.0.0'"
    assert csv[0] == "localhost"
    assert len(csv) == 3
    csv = CommaSeparatedStrings("'localhost', '127.0.0.1', 0.0.0.0")
    assert list(csv) == ["localhost", "127.0.0.1", "0.0.0.0"]
    assert repr(csv) == "CommaSeparatedStrings(['localhost', '127.0.0.1', '0.0.0.0'])"
    assert str(csv) == "'localhost', '127.0.0.1', '0.0.0.0'"
    csv = CommaSeparatedStrings("localhost, 127.0.0.1, 0.0.0.0")
    assert list(csv) == ["localhost", "127.0.0.1", "0.0.0.0"]
    assert repr(csv) == "CommaSeparatedStrings(['localhost', '127.0.0.1', '0.0.0.0'])"
    assert str(csv) == "'localhost', '127.0.0.1', '0.0.0.0'"
    csv = CommaSeparatedStrings(["localhost", "127.0.0.1", "0.0.0.0"])
    assert list(csv) == ["localhost", "127.0.0.1", "0.0.0.0"]
    assert repr(csv) == "CommaSeparatedStrings(['localhost', '127.0.0.1', '0.0.0.0'])"
    assert str(csv) == "'localhost', '127.0.0.1', '0.0.0.0'"


def test_url_query_params():
    u = URL("https://example.org/path/?page=3")
    assert u.query == "page=3"
    u = u.include_query_params(page=4)
    assert str(u) == "https://example.org/path/?page=4"
    u = u.include_query_params(search="testing")
    assert str(u) == "https://example.org/path/?page=4&search=testing"
    u = u.replace_query_params(order="name")
    assert str(u) == "https://example.org/path/?order=name"
    u = u.remove_query_params("order")
    assert str(u) == "https://example.org/path/"


def test_url_blank_params():
    q = QueryParams("a=123&abc&def&b=456")
    assert "a" in q
    assert "abc" in q
    assert "def" in q
    assert "b" in q
    assert len(q.get("abc")) == 0
    assert len(q["a"]) == 3
    assert list(q.keys()) == ["a", "abc", "def", "b"]
