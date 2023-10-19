import enum
import typing
from dataclasses import dataclass, field
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


@dataclass
class MultipartPart(object):
    content_disposition: typing.Optional[bytes] = None
    field_name: str = ""
    data: bytes = b""
    file: typing.Optional[UploadFile] = None
    item_headers: typing.List[typing.Tuple[bytes, bytes]] = field(default_factory=list)


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
        headers: Headers,
        stream: typing.AsyncGenerator[bytes, None],
        *,
        max_files: typing.Union[int, float] = 1000,
        max_fields: typing.Union[int, float] = 1000,
    ) -> None:
        assert (
            multipart is not None
        ), "The `python-multipart` library must be installed to use form parsing"
        self.headers = headers
        self.stream = stream

        self.max_files = max_files
        self.max_fields = max_fields

        self.items: typing.List[typing.Tuple[str, typing.Union[str, UploadFile]]] = []

        self._current_files = 0
        self._current_fields = 0

        self._current_partial_header_name: bytes = b""
        self._current_partial_header_value: bytes = b""
        self._current_part = MultipartPart()

        self._charset = ""

        self._file_parts_to_write: typing.List[typing.Tuple[MultipartPart, bytes]] = []
        self._file_parts_to_finish: typing.List[MultipartPart] = []
        self._files_to_close_on_error: typing.List[SpooledTemporaryFile] = []

    def on_part_begin(self) -> None:
        self._current_part = MultipartPart()

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        message_bytes = data[start:end]
        if self._current_part.file is None:
            self._current_part.data += message_bytes
        else:
            self._file_parts_to_write.append((self._current_part, message_bytes))

    def on_part_end(self) -> None:
        if self._current_part.file is None:
            self.items.append(
                (
                    self._current_part.field_name,
                    _user_safe_decode(self._current_part.data, self._charset),
                )
            )
        else:
            self._file_parts_to_finish.append(self._current_part)
            self.items.append((self._current_part.field_name, self._current_part.file))

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._current_partial_header_name += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._current_partial_header_value += data[start:end]

    def on_header_end(self) -> None:
        field = self._current_partial_header_name.lower()

        if field == b"content-disposition":
            self._current_part.content_disposition = self._current_partial_header_value

        self._current_part.item_headers.append(
            (field, self._current_partial_header_value)
        )
        self._current_partial_header_name = b""
        self._current_partial_header_value = b""

    def on_headers_finished(self) -> None:
        assert self._current_part.content_disposition is not None
        disposition, options = parse_options_header(
            self._current_part.content_disposition
        )

        try:
            self._current_part.field_name = _user_safe_decode(
                options[b"name"], self._charset
            )
        except KeyError:
            raise MultiPartException(
                'The Content-Disposition header field "name" must be provided.'
            )

        if b"filename" in options:
            self._current_files += 1
            if self._current_files > self.max_files:
                raise MultiPartException(
                    f"Too many files. Maximum number of files is {self.max_files}."
                )
            filename = _user_safe_decode(options[b"filename"], self._charset)
            tmpfile = SpooledTemporaryFile(max_size=self.max_file_size)
            self._files_to_close_on_error.append(tmpfile)
            self._current_part.file = UploadFile(
                file=tmpfile,  # type: ignore[arg-type]
                size=0,
                filename=filename,
                headers=Headers(raw=self._current_part.item_headers),
            )
        else:
            self._current_fields += 1
            if self._current_fields > self.max_fields:
                raise MultiPartException(
                    f"Too many fields. Maximum number of fields is {self.max_fields}."
                )
            self._current_part.file = None

    def on_end(self) -> None:
        pass

    async def parse(self) -> FormData:
        _, params = parse_options_header(self.headers["Content-Type"])  # type: ignore
        charset = params.get(b"charset", "utf-8")
        if isinstance(charset, bytes):
            charset = charset.decode("utf-8")

        self._charset = charset
        try:
            boundary = params[b"boundary"]
        except KeyError:
            raise MultiPartException("Missing boundary in multipart.")

        callbacks = {
            "on_part_begin": self.on_part_begin,
            "on_part_data": self.on_part_data,
            "on_part_end": self.on_part_end,
            "on_header_field": self.on_header_field,
            "on_header_value": self.on_header_value,
            "on_header_end": self.on_header_end,
            "on_headers_finished": self.on_headers_finished,
            "on_end": self.on_end,
        }
        parser = multipart.MultipartParser(boundary, callbacks)

        # import logging
        # parser.logger.setLevel(logging.DEBUG)
        try:
            async for chunk in self.stream:
                parser.write(chunk)

                for part, data in self._file_parts_to_write:
                    assert part.file
                    await part.file.write(data)

                for part in self._file_parts_to_finish:
                    assert part.file
                    await part.file.seek(0)

                self._file_parts_to_write.clear()
                self._file_parts_to_finish.clear()
        except MultiPartException as exc:
            for file in self._files_to_close_on_error:
                file.close()
            raise exc
        # end for

        parser.finalize()

        return FormData(self.items)
