import asyncio
import enum
import io
import tempfile
import typing
from urllib.parse import unquote

try:
    import multipart
    from multipart.multipart import parse_options_header
except ImportError as ierr:
    parse_options_header = None
    multipart = None

from yast.datastructures import Headers


class FormMessage(enum.Enum):
    FIELD_START = 1
    FIELD_NAME = 2
    FIELD_DATA = 3
    FIELD_END = 4
    END = 5


class MultiPartMessage(enum.Enum):
    PART_BEGIN = 1
    PART_DATA = 2
    PART_END = 3
    HEADER_FIELD = 4
    HEADER_VALUE = 5
    HEADER_END = 6
    HEADERS_FINISHED = 7
    END = 8


class UploadFile(object):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self._file = io.BytesIO()  # type: typing.IO[typing.Any]
        self._loop = asyncio.get_event_loop()

    def create_tempfile(self) -> None:
        self._file = tempfile.SpooledTemporaryFile()

    async def setup(self) -> None:
        await self._loop.run_in_executor(None, self.create_tempfile)

    async def write(self, data: bytes) -> None:
        await self._loop.run_in_executor(None, self._file.write, data)

    async def read(self, size: int = None) -> None:
        return await self._loop.run_in_executor(None, self._file.read, size)

    async def seek(self, offset: int) -> None:
        await self._loop.run_in_executor(None, self._file.seek, offset)

    async def close(self) -> None:
        await self._loop.run_in_executor(None, self._file.close)


class FormParser(object):
    def __init__(
        self, headers: Headers = None, stream: typing.AsyncGenerator[bytes, None] = None
    ) -> None:
        assert (
            multipart is not None
        ), "The `python-multipart` library must be installed to use form parsing"
        self.headers = headers
        self.stream = stream
        self.messages = []  # type: typing.List[typing.Tuple[FormMessage, bytes]]

    def on_field_start(self) -> None:
        self.messages.append((FormMessage.FIELD_START, b""))

    def on_field_name(self, data: bytes, start: int, end: int) -> None:
        self.messages.append((FormMessage.FIELD_NAME, data[start:end]))

    def on_field_data(self, data: bytes, start: int, end: int) -> None:
        self.messages.append((FormMessage.FIELD_DATA, data[start:end]))

    def on_field_end(self) -> None:
        self.messages.append((FormMessage.FIELD_END, b""))

    def on_end(self) -> None:
        self.messages.append((FormMessage.END, b""))

    async def parse(self) -> typing.Dict[str, typing.Union[str, UploadFile]]:
        callbacks = {
            attr: getattr(self, attr)
            for attr in self.__dir__()
            if attr in ["on_%s" % fm.name.lower() for fm in list(FormMessage)]
        }

        parser = multipart.QuerystringParser(callbacks)
        field_name, field_value = b"", b""
        result = {}
        async for chunk in self.stream():
            if chunk:
                parser.write(chunk)
            else:
                parser.finalize()
            messages = list(self.messages)
            self.messages.clear()
            for msg_type, msg_bytes in messages:
                if msg_type == FormMessage.FIELD_START:
                    field_name, field_value = b"", b""
                elif msg_type == FormMessage.FIELD_NAME:
                    field_name += msg_bytes
                elif msg_type == FormMessage.FIELD_DATA:
                    field_value += msg_bytes
                elif msg_type == FormMessage.FIELD_END:
                    result[field_name.decode("latin-1")] = unquote(
                        field_value.decode("latin-1")
                    )
                elif msg_type == FormMessage.END:
                    pass

        return result


class MultiPartParser(object):
    def __init__(
        self, headers: Headers = None, stream: typing.AsyncGenerator[bytes, None] = None
    ) -> None:
        assert (
            multipart is not None
        ), "The `python-multipart` library must be installed to use form parsing"
        self.headers = headers
        self.stream = stream
        self.messages = []  # type: typing.List[typing.Tuple[MultiPartMessage, bytes]]

    def on_part_begin(self) -> None:
        self.messages.append((MultiPartMessage.PART_BEGIN, b""))

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        self.messages.append((MultiPartMessage.PART_DATA, data[start:end]))

    def on_part_end(self) -> None:
        self.messages.append((MultiPartMessage.PART_END, b""))

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self.messages.append((MultiPartMessage.HEADER_FIELD, data[start:end]))

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self.messages.append((MultiPartMessage.HEADER_VALUE, data[start:end]))

    def on_header_end(self) -> None:
        self.messages.append((MultiPartMessage.HEADER_END, b""))

    def on_headers_finished(self) -> None:
        self.messages.append((MultiPartMessage.HEADERS_FINISHED, b""))

    def on_end(self) -> None:
        self.messages.append((MultiPartMessage.END, b""))

    async def parse(self) -> typing.Dict[str, typing.Union[str, UploadFile]]:
        content_type, params = parse_options_header(self.headers["Content-Type"])
        boundary = params.get(b"boundary")
        _mpm_attrs = ["on_%s" % fm.name.lower() for fm in list(MultiPartMessage)]
        callbacks = {
            attr: getattr(self, attr) for attr in self.__dir__() if attr in _mpm_attrs
        }
        parser = multipart.MultipartParser(boundary, callbacks)
        header_field, header_value = b"", b""
        raw_headers = []
        field_name = ""
        data = b""
        _file = None

        result = {}

        async for chunk in self.stream():
            parser.write(chunk)
            messages = list(self.messages)
            self.messages.clear()

            for msg_type, msg_bytes in messages:
                if msg_type == MultiPartMessage.PART_BEGIN:
                    raw_headers = []
                    data = b""
                elif msg_type == MultiPartMessage.HEADER_FIELD:
                    header_field += msg_bytes
                elif msg_type == MultiPartMessage.HEADER_VALUE:
                    header_value += msg_bytes
                elif msg_type == MultiPartMessage.HEADER_END:
                    raw_headers.append((header_field.lower(), header_value))
                    header_field, header_value = b"", b""
                elif msg_type == MultiPartMessage.HEADERS_FINISHED:
                    headers = Headers(raw=raw_headers)
                    content_disposition = headers.get("Content-Disposition")
                    disposition, options = parse_options_header(content_disposition)
                    field_name = options[b"name"].decode("latin-1")

                    if b"filename" in options:
                        filename = options[b"filename"].decode("latin-1")
                        _file = UploadFile(filename=filename)

                        await _file.setup()
                elif msg_type == MultiPartMessage.PART_DATA:
                    if _file is None:
                        data += msg_bytes
                    else:
                        await _file.write(msg_bytes)
                elif msg_type == MultiPartMessage.PART_END:
                    if _file is None:
                        result[field_name] = data.decode("latin-1")
                    else:
                        await _file.seek(0)
                        result[field_name] = _file
                elif msg_type == MultiPartMessage.END:
                    pass
        parser.finalize()

        return result
