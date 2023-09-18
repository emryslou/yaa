from yast.datastructures.form import *


def test_formdata():
    import io

    upload = io.BytesIO(b"test")
    form = FormData(items=[("a", "123"), ("a", "456"), ("b", upload)])
    assert "a" in form
    assert "A" not in form
    assert "c" not in form
    assert form["a"] == "456"
    assert form.get("a") == "456"
    assert form.get("nope", None) == None
    assert form.getlist("a") == ["123", "456"]
    assert form.keys() == ["a", "b"]
    assert form.values() == ["456", upload]
    assert len(form) == 2
    assert list(form) == ["a", "b"]
    assert dict(form) == {"a": "456", "b": upload}

    assert (
        repr(form)
        == "FormData(items=[('a', '123'), ('a', '456'), ('b', " + repr(upload) + ")])"
    )
    assert FormData(form) == form
    assert FormData({"a": "123", "b": "789"}) == FormData(
        items=[("a", "123"), ("b", "789")]
    )
    assert FormData({"a": "123", "b": "789"}) != {"a": "123", "b": "789"}
