import pytest

from yaa.datastructures.form import *


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
    assert list(form.keys()) == ["a", "b"]
    assert list(form.values()) == ["456", upload]
    assert len(form) == 2
    assert list(form) == ["a", "b"]
    assert dict(form) == {"a": "456", "b": upload}
    assert (
        repr(form)
        == "FormData([('a', '123'), ('a', '456'), ('b', " + repr(upload) + ")])"
    )
    assert FormData(form) == form
    assert FormData({"a": "123", "b": "789"}) == FormData([("a", "123"), ("b", "789")])
    assert FormData({"a": "123", "b": "789"}) != {"a": "123", "b": "789"}


class _TestUploadFile(UploadFile):
    spool_max_size = 1024


@pytest.mark.asyncio
async def test_upload_file():
    big_file = _TestUploadFile("big-file")
    await big_file.write(b"big-data" * 512)
    await big_file.write(b"big-data")
    await big_file.seek(0)
    assert await big_file.read(1024) == b"big-data" * 128
    await big_file.close()


@pytest.mark.anyio
async def test_upload_file_file_input():
    import io
    """Test passing file/stream into the UploadFile constructor"""
    stream = io.BytesIO(b"data")
    file = UploadFile(filename="file", file=stream)
    assert await file.read() == b"data"
    await file.write(b" and more data!")
    assert await file.read() == b""
    await file.seek(0)
    assert await file.read() == b"data and more data!"