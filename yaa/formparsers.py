import enum
import typing
from tempfile import SpooledTemporaryFile
from urllib.parse import unquote_plus

try:
    import multipart
    from multipart.multipart import parse_options_header
except ImportError:  # pragma:nocover
    parse_options_header = None  # pragma:nocover
    multipart = None  # pragma:nocover

from yaa.datastructures import FormData, Headers, UploadFile


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


def _user_safe_decode(src: bytes, codec: str) -> str:
    try:
        return src.decode(codec)
    except (LookupError, UnicodeDecodeError):
        return src.decode("latin-1")


class MultiPartException(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


class FormParser(object):
    def __init__(
        self,
        headers: typing.Optional[Headers] = None,
        stream: typing.Optional[typing.AsyncGenerator[bytes, None]] = None,
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

    async def parse(self) -> FormData:
        callbacks = {
            attr: getattr(self, attr)
            for attr in self.__dir__()
            if attr in [f"on_{fm.name.lower()}" for fm in list(FormMessage)]
        }

        parser = multipart.QuerystringParser(callbacks)
        field_name, field_value = b"", b""
        items: list = []

        if callable(self.stream):
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
                        name = unquote_plus(field_name.decode("utf-8"))
                        value = unquote_plus(field_value.decode("utf-8"))
                        items.append((name, value))
                    # elif msg_type == FormMessage.END:
                    #     pass
                # end for
            # end async for
        # end if

        return FormData(items=items)


class MultiPartParser(object):
    max_file_size = 1024 * 1024

    def __init__(
        self,
        headers: typing.Optional[Headers] = None,
        stream: typing.Optional[typing.AsyncGenerator[bytes, None]] = None,
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

    async def parse(self) -> FormData:
        _, params = parse_options_header(self.headers["Content-Type"])  # type: ignore
        charset = params.get(b"charset", "utf-8")
        if isinstance(charset, bytes):
            charset = charset.decode("utf-8")
        try:
            boundary = params[b"boundary"]
        except KeyError:
            raise MultiPartException("Missing boundary in multipart.")

        _mpm_attrs = [f"on_{fm.name.lower()}" for fm in list(MultiPartMessage)]
        callbacks = {
            attr: getattr(self, attr) for attr in self.__dir__() if attr in _mpm_attrs
        }
        parser = multipart.MultipartParser(boundary, callbacks)
        header_field, header_value = b"", b""
        content_disposition = None
        field_name = ""
        data = b""
        _file = None

        items: list = []
        item_headers: list = []

        if callable(self.stream):
            async for chunk in self.stream():
                parser.write(chunk)
                messages = list(self.messages)
                self.messages.clear()

                for msg_type, msg_bytes in messages:
                    if msg_type == MultiPartMessage.PART_BEGIN:
                        content_disposition = None
                        data = b""
                        item_headers = []
                    elif msg_type == MultiPartMessage.HEADER_FIELD:
                        header_field += msg_bytes
                    elif msg_type == MultiPartMessage.HEADER_VALUE:
                        header_value += msg_bytes
                    elif msg_type == MultiPartMessage.HEADER_END:
                        # raw_headers.append((header_field.lower(), header_value))
                        field = header_field.lower()
                        if field == b"content-disposition":
                            content_disposition = header_value
                        item_headers.append((field, header_value))
                        header_field, header_value = b"", b""
                    elif msg_type == MultiPartMessage.HEADERS_FINISHED:
                        disposition, options = parse_options_header(content_disposition)
                        try:
                            field_name = _user_safe_decode(options[b"name"], charset)
                        except KeyError:
                            raise MultiPartException(
                                'The Content-Disposition header field "name" must be provided.'
                            )
                        if b"filename" in options:
                            filename = _user_safe_decode(options[b"filename"], charset)
                            tmpfile = SpooledTemporaryFile(max_size=self.max_file_size)
                            _file = UploadFile(
                                file=tmpfile,
                                filename=filename,
                                headers=Headers(raw=item_headers),
                            )
                        else:
                            _file = None

                    elif msg_type == MultiPartMessage.PART_DATA:
                        if _file is None:
                            data += msg_bytes
                        else:
                            await _file.write(msg_bytes)
                    elif msg_type == MultiPartMessage.PART_END:
                        if _file is None:
                            items.append((field_name, _user_safe_decode(data, charset)))
                        else:
                            await _file.seek(0)
                            items.append((field_name, _file))
                    # elif msg_type == MultiPartMessage.END:
                    #     pass
                # end for
            # end for
            parser.finalize()
        # end if
        return FormData(items=items)
