"""
module: StaticFiles
title: StaticFiles
description:
    静态文件处理模块，例如: js, html, css, 图片等
    test assddf
author: emryslou@gmail.com
"""


import os
import stat
import typing
from email.utils import parsedate

from aiofiles.os import stat as aio_stat

from yast.datastructures import Headers
from yast.responses import FileResponse, PlainTextResponse, Response
from yast.types import Receive, Scope, Send


class NotModifiedResponse(Response):
    NOT_MODIFIED_HEADERS = (
        "cache-control",
        "content-location",
        "date",
        "etag",
        "expires",
        "vary",
    )

    def __init__(self, headers: Headers) -> None:
        return super().__init__(
            status_code=304,
            headers={
                name: value
                for name, value in headers.items()
                if name in self.NOT_MODIFIED_HEADERS
            },
        )


class StaticFiles(object):
    def __init__(
        self,
        *,
        directory: str = None,
        packages: typing.List[str] = None,
        check_dir: bool = True,
    ) -> None:
        self.directory = directory
        self.packages = packages
        self.all_directories = self.get_directories(directory, packages)
        self.config_checked = False

        if directory is not None and check_dir:
            assert os.path.isdir(directory), f'Directory "{directory}" does not exists'

    def get_directories(
        self, directory: str = None, packages: typing.List[str] = None
    ) -> typing.List[str]:
        directories = []

        if directory is not None:
            directories.append(directory)

        if packages is not None:
            import importlib
            import os

            for package in packages:
                # spec = importlib.util.find_spec(package)
                # assert spec is not None
                # assert spec.origin is not None
                mod = importlib.import_module(package)
                path = mod.__path__[-1]
                directory = os.path.normpath(os.path.join(path, "statics"))
                assert os.path.isdir(directory)
                directories.append(directory)
            # endfor
        # endif
        return directories

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"

        if scope["method"] not in ("GET", "HEAD"):
            res = PlainTextResponse("Method Not Allowed", status_code=405)
            await res(scope=scope, receive=receive, send=send)
            return

        path = os.path.normpath(os.path.join(*scope["path"].split("/")))
        if path.startswith(".."):
            res = PlainTextResponse("Not Found", status_code=404)
            await res(scope=scope, receive=receive, send=send)
            return
        await self.asgi(scope=scope, receive=receive, send=send, path=path)

    async def asgi(self, receive: Receive, send: Send, scope: Scope, path: str) -> None:
        if not self.config_checked:
            await self.check_config()
            self.config_checked = True

        method = scope["method"]
        headers = Headers(scope=scope)
        res = await self.get_response(path, method, headers)

        await res(scope, receive=receive, send=send)

    async def get_response(
        self, path: str, method: str, request_headers: Headers
    ) -> Response:
        stat_result = None
        for directory in self.all_directories:
            full_path = os.path.join(directory, path)
            try:
                stat_result = await aio_stat(full_path)
            except FileNotFoundError:
                pass
            else:
                break

        if stat_result is None or not os.path.isfile(full_path):
            return PlainTextResponse("Not Found", status_code=404)

        res = FileResponse(full_path, stat_result=stat_result)
        if self.is_not_modified(res.headers, request_headers):
            return NotModifiedResponse(res.headers)

        return res

    def is_not_modified(
        self, response_headers: Headers, request_headers: Headers
    ) -> bool:
        try:
            if_none_match = request_headers["if-none-match"]
            etag = response_headers["etag"]
            if if_none_match == etag:
                return True
        except KeyError:
            pass

        try:
            if_modified_since = parsedate(request_headers["if-modified-since"])
            last_modified = parsedate(response_headers["last-modified"])
            if (
                if_modified_since is not None
                and last_modified is not None
                and if_modified_since >= last_modified
            ):
                return True
        except KeyError:
            pass

        return False

    async def check_config(self) -> None:
        if self.directory is None:
            return

        try:
            stat_result = await aio_stat(self.directory)
        except FileNotFoundError:
            raise RuntimeWarning(
                f"StaticFile directory `{self.directory}` does not exists"
            )

        if not (stat.S_ISDIR(stat_result.st_mode) or stat.S_ISLNK(stat_result.st_mode)):
            raise RuntimeWarning(
                f"StaticFile directory `{self.directory}` is not a directory"
            )
