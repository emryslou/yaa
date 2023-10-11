import functools
import hashlib
import http.cookies
import json
import os
import stat
import sys
import typing
from email.utils import formatdate
from mimetypes import guess_type as mimetypes_guess_type
from urllib.parse import quote

import anyio

from yaa.background import BackgroundTask
from yaa.concurrency import iterate_in_threadpool
from yaa.datastructures import URL, MutableHeaders
from yaa.types import Receive, Scope, Send

try:
    import aiofiles
except ImportError:  # pragma: nocover
    aiofiles = None  # type: ignore

try:
    import ujson
except ImportError:  # pragma: nocover
    ujson = None  # type: ignore


def guess_type(
    url: typing.Union[str, "os.PathLike[str]"], strict: bool = True
) -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
    if sys.version_info < (3, 8):  # pragma: no cover
        url = os.fspath(url)  # pragma: no cover
    return mimetypes_guess_type(url, strict)


http.cookies.Morsel._reserved["samesite"] = "SameSite"


class Response(object):
    media_type = None
    charset = "utf-8"

    def __init__(
        self,
        content: typing.Any = None,
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
        background: BackgroundTask = None,
    ) -> None:
        self.status_code = status_code
        if media_type is not None:
            self.media_type = media_type
        self.background = background
        self.body = self.render(content)
        self.init_headers(headers)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.get_send_headers(scope),
            }
        )
        if scope["method"] not in ("HEAD"):
            await send({"type": "http.response.body", "body": self.body})
        else:
            await send({"type": "http.response.body"})

        if self.background is not None:
            await self.background()

    def get_send_headers(self, scope: Scope):
        import warnings

        warnings.warn(
            "know issue: `AttributeError: '_MockOriginalResponse' object has no attribute 'close'. Did you mean: 'closed'?` when content-length not eq 0 at request of head method"
        )
        _headers = []
        for key in self.headers:
            if scope["method"] in ("HEAD"):
                if key.encode().lower() == b"content-length":
                    value = b"0"
                else:
                    value = self.headers[key]
            else:
                value = self.headers[key]
            if isinstance(value, bytes):
                value = value.decode()
            _headers.append([key.encode(), value.encode()])

        return _headers

    def render(self, content: typing.Any) -> bytes:
        if content is None:
            content = b""
        if isinstance(content, bytes):
            return content
        return content.encode(self.charset)

    def init_headers(self, headers: dict = None):
        if headers is None:
            raw_headers = []  # type: typing.List[typing.Tuple[bytes, bytes]]
            missing_content_length = True
            missing_content_type = True
        else:
            raw_headers = [
                (h_k.lower().encode("latin-1"), h_v.encode("latin-1"))
                for h_k, h_v in headers.items()
            ]
            keys = [h[0] for h in raw_headers]
            missing_content_length = b"content-length" not in keys
            missing_content_type = b"content-type" not in keys

        body = getattr(self, "body", b"")
        if body and missing_content_length:
            raw_headers.append((b"content-length", str(len(body)).encode("latin-1")))

        content_type = self.media_type
        if content_type is not None and missing_content_type:
            if content_type.startswith("text/"):
                content_type += f"; charset={self.charset}"
            raw_headers.append((b"content-type", content_type.encode("latin-1")))

        self.raw_headers = raw_headers

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: int = None,
        expires: int = None,
        path: str = None,
        domain: str = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str = "lax",
    ) -> None:
        cookie = http.cookies.SimpleCookie()
        cookie[key] = value
        if max_age is not None:
            cookie[key]["max-age"] = max_age
        if expires is not None:
            cookie[key]["expires"] = expires
        if path is not None:
            cookie[key]["path"] = path
        if domain is not None:
            cookie[key]["domain"] = domain
        if secure:
            cookie[key]["secure"] = True
        if httponly:
            cookie[key]["httponly"] = True
        if samesite is not None:
            assert samesite.lower() in (
                "strict",
                "lax",
                "none",
            ), "samesite must be either `strict`, `lax` or `none`"
            cookie[key]["samesite"] = samesite

        cookie_val = cookie.output(header="").strip()
        self.raw_headers.append((b"set-cookie", cookie_val.encode("latin-1")))

    def del_cookie(
        self,
        key: str,
        path: str = "/",
        domain: str = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str = "lax",
    ) -> None:
        self.set_cookie(
            key,
            expires=0,
            max_age=0,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
        )

    @property
    def headers(self):
        if not hasattr(self, "_headers"):
            self._headers = MutableHeaders(raw=self.raw_headers)
        return self._headers


class HTMLResponse(Response):
    media_type = "text/html"


class PlainTextResponse(Response):
    media_type = "text/plain"


class JSONResponse(Response):
    media_type = "application/json"

    def render(self, content: typing.Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


class UJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
        assert (
            ujson is not None
        ), "`usjon` must be required for `UJSONResponse`, maybe try `pip install ujson`"
        return ujson.dumps(
            content,
            ensure_ascii=False,
        ).encode("utf-8")


class StreamingResponse(Response):
    def __init__(
        self,
        content: typing.Any,
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
        background: BackgroundTask = None,
    ) -> None:
        if isinstance(content, typing.AsyncIterable):
            self.body_iter = content
        else:
            self.body_iter = iterate_in_threadpool(content)
        self.status_code = status_code
        self.media_type = self.media_type if media_type is None else media_type
        self.background = background
        self.init_headers(headers)

    async def listen_for_disconnect(self, receive: Receive) -> None:
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break

    async def response(self, send: Send, scope: Scope) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.get_send_headers(scope),
            }
        )
        if scope["method"] not in ("HEAD"):
            async for chunk in self.body_iter:
                if not isinstance(chunk, bytes):
                    chunk = chunk.encode(self.charset)
                await send(
                    {"type": "http.response.body", "body": chunk, "more_body": True}
                )
            await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async with anyio.create_task_group() as tg:

            async def wrap(func: typing.Callable[[], typing.Coroutine]) -> None:
                await func()
                tg.cancel_scope.cancel()

            tg.start_soon(wrap, functools.partial(self.response, send, scope))
            await wrap(functools.partial(self.listen_for_disconnect, receive))

        if self.background is not None:
            await self.background()


class FileResponse(Response):
    """File Response"""

    chunk_size = 4096

    def __init__(
        self,
        path: typing.Union[str, "os.PathLike[str]"],
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
        background: BackgroundTask = None,
        filename: str = None,
        stat_result: os.stat_result = None,
    ) -> None:
        assert aiofiles is not None, "'aiofiles' must be installed to use FileResponse"
        self.path = path
        self.status_code = status_code
        self.filename = filename
        if media_type is None:
            media_type = guess_type(filename or path)[0] or "text/plain"

        self.media_type = media_type
        self.background = background
        self.init_headers(headers)
        if self.filename is not None:
            content_disposition_name = quote(self.filename)
            if content_disposition_name != self.filename:
                content_disposition = (
                    "attachment; filename*=utf-8''" f"{content_disposition_name}"
                )
            else:
                content_disposition = f'attachment; filename="{self.filename}"'
            self.headers.setdefault("content-disposition", content_disposition)

        self.stat_result = stat_result
        if stat_result is not None:
            self.set_stat_headers(stat_result)

    def set_stat_headers(self, stat_result: os.stat_result):
        stat_headers = self.get_stat_headers(stat_result)
        for _name, _value in stat_headers.items():
            self.headers.setdefault(_name, _value)

    @classmethod
    def get_stat_headers(cls, stat_result: os.stat_result) -> typing.Dict[str, str]:
        content_length = str(stat_result.st_size)
        last_modified = formatdate(stat_result.st_mtime, usegmt=True)
        etag_base = str(stat_result.st_mtime) + "-" + str(stat_result.st_size)
        etag = hashlib.md5(etag_base.encode()).hexdigest()
        return {
            "content-length": content_length,
            "last-modified": last_modified,
            "etag": etag,
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.stat_result is None:
            try:
                stat_result = await anyio.to_thread.run_sync(os.stat, self.path)
                self.set_stat_headers(stat_result)
            except FileNotFoundError:
                raise RuntimeError(f"File at path {self.path} does not exists.")
            else:
                mode = stat_result.st_mode
                if not stat.S_ISREG(mode):
                    raise RuntimeError(f"File at path {self.path} is not a file.")

        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.get_send_headers(scope),
            }
        )
        if scope["method"] in ("HEAD"):
            await send({"type": "http.response.body", "body": b"", "more_body": False})
        else:
            async with await anyio.open_file(self.path, mode="rb") as file:
                more_body = True
                while more_body:
                    chunk = await file.read(self.chunk_size)
                    more_body = len(chunk) == self.chunk_size
                    await send(
                        {
                            "type": "http.response.body",
                            "body": chunk,
                            "more_body": more_body,
                        }
                    )

        if self.background is not None:
            await self.background()


class RedirectResponse(Response):
    def __init__(
        self,
        url: typing.Union[str, URL],
        status_code=307,
        headers: dict = None,
        background: BackgroundTask = None,
    ) -> None:
        super().__init__(
            b"", status_code=status_code, headers=headers, background=background
        )

        self.headers["location"] = quote(str(url), safe=":/%#?=@[]!$&'()*+,;")
