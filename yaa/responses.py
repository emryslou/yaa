"""
module: Response
title: 路由控制模块
description:
    Http 响应对象，挂载到路由 route 的 API 均需返回响应对象， 主要包含如下:
    - Response: 响应对象基础类，所有响应对象的实现必须继承该对象
    - HTMLResponse: html 响应对象
    - PlainTextResponse: text 响应对象
    - JSONResponse: json 响应对象
    - UJSONResponse: json 响应对象, 通过 ujson 实现
    - StreamingResponse: 流响应对象
    - FileResponse: 文件响应
    - RedirectResponse: 重定向
author: emryslou@gmail.com
examples: test_responses.py
"""
import functools
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

from yaa._compat import md5_hexdigest
from yaa.background import BackgroundTask
from yaa.concurrency import iterate_in_threadpool
from yaa.datastructures import URL, MutableHeaders
from yaa.types import Receive, Scope, Send

try:
    import aiofiles  # type: ignore
except ImportError:  # pragma: nocover
    aiofiles = None  # type: ignore

try:
    import ujson  # type: ignore
except ImportError:  # pragma: nocover
    ujson = None  # type: ignore


def guess_type(
    url: typing.Union[str, "os.PathLike[str]"], strict: bool = True
) -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
    if sys.version_info < (3, 8):  # pragma: no cover
        url = os.fspath(url)  # pragma: no cover
    return mimetypes_guess_type(url, strict=strict)


http.cookies.Morsel._reserved["samesite"] = "SameSite"  # type: ignore


class Response(object):
    media_type = None
    charset = "utf-8"

    def __init__(
        self,
        content: typing.Optional[typing.Any] = None,
        status_code: int = 200,
        headers: typing.Optional[dict] = None,
        media_type: typing.Optional[str] = None,
        background: typing.Optional[BackgroundTask] = None,
    ) -> None:
        """Response:
        param: content: 响应内容
        param: status_code: http 响应码, 更多 @see https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
        param: headers: 响应头
        param: media_type: 媒体类型，响应数据类型
        param: background: 响应后，后台执行的任务
        """

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

    def get_send_headers(self, scope: Scope) -> typing.List:
        import warnings

        warnings.warn(
            "know issue: `AttributeError: '_MockOriginalResponse' object has no attribute 'close'. Did you mean: 'closed'?` when content-length not eq 0 at request of head method"
        )
        _headers = []
        for key in self.headers:
            if scope["method"] in ("HEAD"):
                if key.encode().lower() == b"content-length":
                    value = "0"
                else:
                    value = self.headers[key]
            else:
                value = self.headers[key]
            if isinstance(value, bytes):
                value = value.decode()  # type: ignore
            _headers.append([key.encode(), value.encode()])  # type: ignore

        return _headers

    def render(self, content: typing.Any) -> bytes:
        """设置响应内容
        param: content: 响应内容
        """
        if content is None:
            content = b""
        if isinstance(content, bytes):
            return content
        return content.encode(self.charset)

    def init_headers(self, headers: typing.Optional[dict] = None) -> None:
        """设置响应头
        param: headers: 响应头
        """
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

        body = getattr(self, "body", None)
        if (
            body is not None
            and missing_content_length
            and not (self.status_code < 200 or self.status_code in (204, 304))
        ):
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
        value: typing.Optional[str] = "",
        max_age: typing.Optional[int] = None,
        expires: typing.Optional[int] = None,
        path: typing.Optional[str] = None,
        domain: typing.Optional[str] = None,
        secure: typing.Optional[bool] = False,
        httponly: typing.Optional[bool] = False,
        samesite: typing.Optional[str] = "lax",
    ) -> None:
        """添加cookie
        param: key: cookie 键
        param: value: cookie 值
        param: max_age: cookie 存活时间，单位: 秒(second)，负数或者 0 则立即失效
        param: expires: cookie 存活时间戳，单位: 秒(second), 注意: max_age 和 expires 同时设置，则 以 max_age 优先
        """
        cookie: dict = http.cookies.SimpleCookie()
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

        cookie_val = cookie.output(header="").strip()  # type: ignore
        self.raw_headers.append((b"set-cookie", cookie_val.encode("latin-1")))

    def del_cookie(
        self,
        key: str,
        path: str = "/",
        domain: typing.Optional[str] = None,
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
    def headers(self) -> MutableHeaders:
        if not hasattr(self, "_headers"):
            self._headers = MutableHeaders(raw=self.raw_headers)
        return self._headers


class HTMLResponse(Response):
    media_type = "text/html"


class PlainTextResponse(Response):
    media_type = "text/plain"


class JSONResponse(Response):
    media_type = "application/json"

    def __init__(
        self,
        content: typing.Any,
        status_code: int = 200,
        headers: typing.Optional[dict] = None,
        media_type: typing.Optional[str] = None,
        background: typing.Optional[BackgroundTask] = None,
    ) -> None:
        super().__init__(content, status_code, headers, media_type, background)

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
        headers: typing.Optional[dict] = None,
        media_type: typing.Optional[str] = None,
        background: typing.Optional[BackgroundTask] = None,
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

    chunk_size = 64 * 1024

    def __init__(
        self,
        path: typing.Union[str, "os.PathLike[str]"],
        status_code: int = 200,
        headers: typing.Optional[dict] = None,
        media_type: typing.Optional[str] = None,
        background: typing.Optional[BackgroundTask] = None,
        filename: typing.Optional[str] = None,
        stat_result: typing.Optional[os.stat_result] = None,
        content_disposition_type: str = "attachment",  # `inline` or `attachment` @see https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Disposition
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
                content_disposition = "{}; filename*=utf-8''{}".format(
                    content_disposition_type, content_disposition_name
                )
            else:
                content_disposition = '{}; filename="{}"'.format(
                    content_disposition_type, self.filename
                )
            self.headers.setdefault("content-disposition", content_disposition)

        self.stat_result = stat_result
        if stat_result is not None:
            self.set_stat_headers(stat_result)

    def set_stat_headers(self, stat_result: os.stat_result) -> None:
        stat_headers = self.get_stat_headers(stat_result)
        for _name, _value in stat_headers.items():
            self.headers.setdefault(_name, _value)

    @classmethod
    def get_stat_headers(cls, stat_result: os.stat_result) -> typing.Dict[str, str]:
        content_length = str(stat_result.st_size)
        last_modified = formatdate(stat_result.st_mtime, usegmt=True)
        etag_base = str(stat_result.st_mtime) + "-" + str(stat_result.st_size)
        etag = md5_hexdigest(etag_base.encode())
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
        status_code: int = 307,
        headers: typing.Optional[dict] = None,
        background: typing.Optional[BackgroundTask] = None,
    ) -> None:
        super().__init__(
            b"", status_code=status_code, headers=headers, background=background
        )

        self.headers["location"] = quote(str(url), safe=":/%#?=@[]!$&'()*+,;")
