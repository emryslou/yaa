from yast.datastructures.types import *


def test_multidict():
    q = MultiDict([("a", "123"), ("a", "456"), ("b", "789")])

    assert "a" in q
    assert "A" not in q
    assert "c" not in q
    assert q["a"] == "456"
    assert q.get("a") == "456"
    assert q.get("nope", None) == None
    assert q.getlist("a") == ["123", "456"]
    assert list(q.keys()) == ["a", "b"]
    assert list(q.values()) == ["456", "789"]
    assert list(q.items()) == [("a", "456"), ("b", "789")]
    assert len(q) == 2
    assert list(q) == ["a", "b"]
    assert dict(q) == {"a": "456", "b": "789"}
    assert str(q) == "MultiDict([('a', '123'), ('a', '456'), ('b', '789')])"
    assert repr(q) == "MultiDict([('a', '123'), ('a', '456'), ('b', '789')])"
    assert MultiDict({"a": "123", "b": "456"}) == MultiDict(
        [("a", "123"), ("b", "456")]
    )
    assert MultiDict({"a": "123", "b": "456"}) == MultiDict(
        [("a", "123"), ("b", "456")]
    )
    assert MultiDict({"a": "123", "b": "456"}) == MultiDict({"b": "456", "a": "123"})
    assert MultiDict() == MultiDict({})
    assert MultiDict({"a": "123", "b": "456"}) != "invalid"
    q = MultiDict([("a", "123"), ("a", "456")])
    assert MultiDict(q) == q
    q = MultiDict([("a", "123"), ("a", "456")])
    q["a"] = "789"
    assert q["a"] == "789"
    assert q.getlist("a") == ["789"]
    q = MultiDict([("a", "123"), ("a", "456")])
    del q["a"]
    assert q.get("a") is None
    assert repr(q) == "MultiDict([])"
    q = MultiDict([("a", "123"), ("a", "456"), ("b", "789")])
    assert q.pop("a") == "456"
    assert q.get("a", None) is None
    assert repr(q) == "MultiDict([('b', '789')])"
    q = MultiDict([("a", "123"), ("a", "456"), ("b", "789")])
    item = q.popitem()
    assert q.get(item[0]) is None
    q = MultiDict([("a", "123"), ("a", "456"), ("b", "789")])
    assert q.poplist("a") == ["123", "456"]
    assert q.get("a") is None
    assert repr(q) == "MultiDict([('b', '789')])"
    q = MultiDict([("a", "123"), ("a", "456"), ("b", "789")])
    q.clear()
    assert q.get("a") is None
    assert repr(q) == "MultiDict([])"
    q = MultiDict([("a", "123")])
    q.setlist("a", ["456", "789"])
    assert q.getlist("a") == ["456", "789"]
    q.setlist("b", [])
    assert q.get("b") is None
    q = MultiDict([("a", "123")])
    assert q.setdefault("a", "456") == "123"
    assert q.getlist("a") == ["123"]
    assert q.setdefault("b", "456") == "456"
    assert q.getlist("b") == ["456"]
    assert repr(q) == "MultiDict([('a', '123'), ('b', '456')])"
    q = MultiDict([("a", "123")])
    q.appendlist("a", "456")
    assert q.getlist("a") == ["123", "456"]
    assert repr(q) == "MultiDict([('a', '123'), ('a', '456')])"
    q = MultiDict([("a", "123"), ("b", "456")])
    q.update({"a": "789"})
    assert q.getlist("a") == ["789"]
    q == MultiDict([("a", "789"), ("b", "456")])
    q = MultiDict([("a", "123"), ("b", "456")])
    q.update(q)
    assert repr(q) == "MultiDict([('a', '123'), ('b', '456')])"
    q = MultiDict([("a", "123"), ("b", "456")])
    q.update(None)
    assert repr(q) == "MultiDict([('a', '123'), ('b', '456')])"
    q = MultiDict([("a", "123"), ("a", "456")])
    q.update([("a", "123")])
    assert q.getlist("a") == ["123"]
    q.update([("a", "456")], a="789", b="123")
    assert q == MultiDict([("a", "456"), ("a", "789"), ("b", "123")])
