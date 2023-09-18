from yast.datastructures.headers import *


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


def test_mutabheaders():
    mh = MutableHeaders(raw=[(b"aa", b"123"), (b"bb", b"234")])
    del mh["aa"]
    assert dict(mh) == {"bb": "234"}
    mh.setdefault("CC", value="xxx")
    assert dict(mh) == {"bb": "234", "cc": "xxx"}
