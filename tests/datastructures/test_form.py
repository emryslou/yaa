import pytest
import io
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

    stream = io.BytesIO(b"data")
    upload = UploadFile(filename="file", file=stream, size=4)
    form = FormData([("a", "123"), ("a", "456"), ("b", upload)])
    assert "a" in form
    assert "A" not in form


@pytest.mark.anyio
async def test_upload_file_file_input():
    """Test passing file/stream into the UploadFile constructor"""

    stream = io.BytesIO(b"data")
    file = UploadFile(filename="file", file=stream, size=4)
    assert await file.read() == b"data"
    assert file.size == 4
    await file.write(b" and more data!")
    assert await file.read() == b""
    assert file.size == 19
    await file.seek(0)
    assert await file.read() == b"data and more data!"


@pytest.mark.anyio
async def test_upload_file_without_size():
    """Test passing file/stream into the UploadFile constructor without size"""
    stream = io.BytesIO(b"data")
    file = UploadFile(filename="file", file=stream)
    assert await file.read() == b"data"
    assert file.size is None
    await file.write(b" and more data!")
    assert await file.read() == b""
    assert file.size is None
    await file.seek(0)
    assert await file.read() == b"data and more data!"


@pytest.mark.anyio
@pytest.mark.parametrize("max_size", [1, 1024], ids=["rolled", "unrolled"])
async def test_uploadfile_rolling(max_size: int) -> None:
    """Test that we can r/w to a SpooledTemporaryFile
    managed by UploadFile before and after it rolls to disk
    """
    from tempfile import SpooledTemporaryFile

    stream: BinaryIO = SpooledTemporaryFile(max_size=max_size)
    file = UploadFile(filename="file", file=stream, size=0)
    assert await file.read() == b""
    assert file.size == 0
    await file.write(b"data")
    assert await file.read() == b""
    assert file.size == 4
    await file.seek(0)
    assert await file.read() == b"data"
    await file.write(b" more")
    assert await file.read() == b""
    assert file.size == 9
    await file.seek(0)
    assert await file.read() == b"data more"
    assert file.size == 9
    await file.close()
