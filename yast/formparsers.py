import asyncio
import enum
import tempfile
import typing

from yast.datastructures import Headers


try:
    from multipart.multipart import parse_options_header
    import multipart
except ImportError as ierr:
    print('import error', ierr)
    parse_options_header = None
    multipart = None 


class FormMessage(enum.Enum):
    FIELD_START = 1
    FIELD_NAME  = 2
    FIELD_DATA  = 3
    FIELD_END   = 4
    END         = 5


class MultiPartMessage(enum.Enum):
    PART_BEGIN          = 1
    PART_DATA           = 2
    PART_END            = 3
    HEADER_FIELD        = 4
    HEADER_VALUE        = 5
    HEADER_END          = 6
    HEADERS_FINISHED    = 7
    END                 = 8


class UploadFile(object):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self._file = None
        self._loop = asyncio.get_event_loop()
    
    async def setup(self) -> None:
        self._file = await self._loop.run_in_executor(
                None,
                tempfile.SpooledTemporaryFile
            )
    
    async def write(self, data: bytes) -> None:
        await self._loop.run_in_executor(None, self._file.write, data)
    
    async def read(self, size: int = None) -> None:
        await self._loop.run_in_executor(None, self._file.read, size)
    
    async def seek(self, offset: int) -> None:
        await self._loop.run_in_executor(None, self._file.seek, offset)
    
    async def close(self, offset: int) -> None:
        await self._loop.run_in_executor(None, self._file.close)


class FormParser(object):
    def __init__(
            self, headers: Headers = None, 
            stream: typing.AsyncGenerator[bytes, None] = None
        ) -> None:
        assert multipart is not None, 'The `python-multipart` library must be installed to use form parsing'
        self.headers = headers
        self.stream = stream
        self.messages = [] # type: typing.List[typing.Tuple[MultiPartMessage, bytes]]
    

    def on_field_start(self, data: bytes, start: int, end: int) -> None:
        print('debug -- 900 on field start')
        self.messages.append((FormMessage.FIELD_START, data[start:end]))

    
    def on_field_name(self, data: bytes, start: int, end: int) -> None:
        print('debug -- 901 on field name')
        self.messages.append((FormMessage.FIELD_NAME, data[start:end]))


    def on_field_data(self, data: bytes, start: int, end: int) -> None:
        print('debug -- 902 on field data')
        self.messages.append((FormMessage.FIELD_DATA, data[start:end]))
    

    def on_field_end(self) -> None:
        print('debug -- 903 on field data')
        self.messages.append((FormMessage.FIELD_END, b''))
    
    def on_end(self) -> None:
        print('debug -- 903 on end')
        self.messages.append((FormMessage.END, b''))
    
    async def parse(self) -> typing.Dict[str,typing.Union[str, UploadFile]]:
        callbacks = {
            attr: getattr(self, attr)
            for attr in self.__dir__()
            if attr in [
                'on_%s'%fm.name.lower() 
                for fm in list(FormMessage)
            ]
        }
        
        parser = multipart.QuerystringParser(callbacks)
        field_name, field_value = b'', b''
        result = {}
        async for chunk in self.stream():
            if chunk:
                parser.write(chunk)
            else:
                parser.finalize()
            messages = list(self.messages)
            self.messages.clear()
            for msg_type, msg_bytes in messages:
                if msg_type == FormMessage.FIELD_DATA:
                    field_name, field_value = b'', b''
                elif msg_type == FormMessage.FIELD_NAME:
                    field_name += msg_bytes
                elif msg_type == FormMessage.FIELD_DATA:
                    field_value += msg_bytes
                elif msg_type == FormMessage.FIELD_END:
                    result[field_name.decode('latin-1')] = field_value.decode('latin-1')
                elif msg_type == FormMessage.END:
                    pass
        
        return result


class MultiPartParser(object):
    def __init__(
            self, headers: Headers = None, 
            stream: typing.AsyncGenerator[bytes, None] = None
        ) -> None:
        assert multipart is not None, 'The `python-multipart` library must be installed to use form parsing'
        self.headers = headers
        self.stream = stream
        self.messages = [] # type: typing.List[typing.Tuple[MultiPartMessage, bytes]]
    
    def on_part_begin(self) -> None:
        self.messages.append((MultiPartMessage.PART_BEGIN, b''))
    
    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        self.messages.append((MultiPartMessage.PART_DATA, data[start:end]))
    
    def on_part_end(self) -> None:
        self.messages.append((MultiPartMessage.PART_END, b''))

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self.messages.append((MultiPartMessage.HEADER_FIELD, data[start:end]))

