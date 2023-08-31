import hashlib
import os
import stat
import typing

from email.utils import formatdate
from mimetypes import guess_type
from urllib.parse import quote_plus

from yast.types import Receive, Send
from yast.datastructures import MutableHeaders
from yast.types import Receive, Send

try:
    import aiofiles
    from aiofiles.os import stat as aio_stat
except ImportError: # pragma: nocover
    aiofiles = None
    aio_stat = None

try:
    import ujson as json
    JSON_DUMPS_OPTIONS = {'ensure_ascii': False}
except ImportError: # pragma: nocover
    import json
    JSON_DUMPS_OPTIONS = {
        'ensure_ascii': False,
        'allow_nan': False,
        'indent': None,
        'separators': (',', ':')
    }

class Response:
    media_type = None
    charset = "utf-8"

    def __init__(
        self,
        content: typing.Any,
        status_code: int = 200,
        headers: dict = None, # todo
        media_type: str = None,
    ) -> None:
        self.body = self.render(content)
        self.status_code = status_code
        if media_type is not None:
            self.media_type = media_type
        self.init_headers(headers)

    async def __call__(self, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [
                    [key.encode(), value.encode()] for key, value in self.headers
                ],
            }
        )
        await send({"type": "http.response.body", "body": self.body})

    def render(self, content: typing.Any) -> bytes:
        if isinstance(content, bytes):
            return content
        return content.encode(self.charset)

    def init_headers(self, headers: dict = None):
        if headers is None:
            raw_headers = []
            missing_content_length = True
            missing_content_type = True
        else:
            raw_headers = [
                (h_k.lower().encode('latin-1'), h_v.encode('latin-1'))
                for h_k, h_v in headers.items()
            ]
            keys = [h[0] for h in raw_headers]
            missing_content_length = b'content-length' not in keys
            missing_content_type = b'content-type' not in keys

        body = getattr(self, 'body', None)
        if body is not None and missing_content_length:
            raw_headers.append((b'content-length', str(len(body)).encode('latin-1')))
        
        content_type = self.media_type
        if content_type is not None and missing_content_type:
            if content_type.startswith('text/'):
                content_type += '; charset=%s' % self.charset
            raw_headers.append((b'content-type', content_type.encode('latin-1')))

        self.raw_headers = raw_headers

    @property
    def headers(self):
        if not hasattr(self, '_headers'):
            self._headers = MutableHeaders(self.raw_headers)
        return self._headers

class HTMLResponse(Response):
    media_type = "text/html"


class PlainTextResponse(Response):
    media_type = 'text/plain'


class JSONResponse(Response):
    media_type = "application/json"

    def render(self, content: typing.Any) -> bytes:
        return json.dumps(content, **JSON_DUMPS_OPTIONS).encode("utf-8")


class StreamingResponse(Response):
    def __init__(
        self,
        content: typing.Any,
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
    ) -> None:
        self.body_iter = content
        self.status_code = status_code
        if media_type:
            self.media_type = media_type

        self.init_headers(headers)

    async def __call__(self, receive: Receive, send: Send):
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [
                    [key.encode(), value.encode()] for key, value in self.headers
                ],
            }
        )

        async for chunk in self.body_iter:
            if not isinstance(chunk, bytes):
                chunk = chunk.encode(self.charset)
            await send({ "type": "http.response.body", "body": chunk, "more_body": True })
        await send({ "type": "http.response.body", "body": b"", "more_body": False })


class FileResponse(Response):
    """ File Response """
    chunk_size = 4096

    def __init__(
            self,
            path: str,
            headers: dict = None,
            media_type: str = None,
            filename: str = None,
            stat_result: os.stat_result = None
        ) -> None:
        assert aiofiles is not None, "'aiofiles' must be installed to use FileResponse"
        self.path = path
        self.status_code = 200
        self.filename = filename
        if media_type is None:
            media_type = guess_type(filename or path)[0] or 'text/plain'
        
        self.media_type = media_type
        self.init_headers(headers)
        if self.filename is not None:
            content_disposition = f'attachment; filename="{self.filename}"'
            self.headers.setdefault('content-disposition', content_disposition)
        
        self.stat_result = stat_result
        if stat_result is not None:
            self.set_stat_headers(stat_result)
    
    def set_stat_headers(self, stat_result: os.stat_result):
        content_length = str(stat_result.st_size)
        last_modified = formatdate(stat_result.st_mtime, usegmt=True)
        etag_base = str(stat_result.st_mtime) + '-' + str(stat_result.st_size)
        etag = hashlib.md5(etag_base.encode()).hexdigest()

        self.headers.setdefault("content-length", content_length)
        self.headers.setdefault("last-modified", last_modified)
        self.headers.setdefault("etag", etag)

    async def __call__(self, receive: Receive, send: Send) -> None:
        if self.stat_result is None:
            stat_result = await aio_stat(self.path)
            self.set_stat_headers(stat_result)
            
        await send({
            'type': 'http.response.start',
            'status': self.status_code,
            'headers': self.raw_headers,
        })

        async with aiofiles.open(self.path, mode='rb') as file:
            more_body = True
            while more_body:
                chunk = await file.read(self.chunk_size)
                more_body = len(chunk) == self.chunk_size
                await send({
                    'type': 'http.response.body',
                    'body': chunk,
                    'more_body': more_body,
                })


class RedirectResponse(Response):
    def __init__(self, url: str, status_code=302, headers: dict =None):
        super().__init__(b'', status_code=status_code, headers=headers)

        #todo: why: '&' repeat 
        self.headers['location'] = quote_plus(url, safe=":/#?&=@[]!$&'()*+,;")