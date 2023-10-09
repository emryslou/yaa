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

from yaa.datastructures import Headers
from yaa.responses import (
    FileResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from yaa.types import Receive, Scope, Send

PathLike = typing.Union[str, "os.PathLike[str]"]


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
        super().__init__(
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
        directory: PathLike = None,
        packages: typing.List[str] = None,
        html: bool = False,
        check_dir: bool = True,
    ) -> None:
        self.directory = directory
        self.packages = packages
        self.all_directories = self.get_directories(directory, packages)
        self.html = html
        self.config_checked = False

        if directory is not None and check_dir:
            assert os.path.isdir(directory), f'Directory "{directory}" does not exists'

    def get_directories(
        self, directory: PathLike = None, packages: typing.List[str] = None
    ) -> typing.List[PathLike]:
        directories = []

        if directory is not None:
            directories.append(directory)

        if packages is not None:
            import importlib
            import os

            for package in packages or []:
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

        path = self.get_path(scope)
        res = await self.get_response(path, scope)
        await res(scope, receive=receive, send=send)

    def get_path(self, scope: Scope) -> str:
        return os.path.normpath(os.path.join(*scope["path"].split("/")))

    async def get_response(
        self,
        path: PathLike,
        scope: Scope,
    ) -> Response:
        if scope["method"] not in ("GET", "HEAD"):
            return PlainTextResponse("Method Not Allowed", status_code=405)

        if not self.config_checked:
            await self.check_config()
            self.config_checked = True

        full_path, stat_result = await self.lookup_path(path)
        if stat_result and stat.S_ISREG(stat_result.st_mode):
            return self.file_response(full_path, stat_result, scope=scope)

        elif stat_result and stat.S_ISDIR(stat_result.st_mode) and self.html:
            index_path = os.path.join(path, "index.html")
            full_path, stat_result = await self.lookup_path(index_path)
            if stat_result is not None and stat.S_ISREG(stat_result.st_mode):
                if not scope["path"].endswith("/"):
                    from yaa.datastructures import URL

                    url = URL(scope=scope)
                    url = url.replace(path=url.path + "/")
                    return RedirectResponse(url)
                return self.file_response(full_path, stat_result, scope)

        if self.html:
            full_path, stat_result = await self.lookup_path("404.html")
            if stat_result is not None and stat.S_ISREG(stat_result.st_mode):
                return FileResponse(full_path, stat_result=stat_result, status_code=404)

        return PlainTextResponse("Not Found", status_code=404)

    async def lookup_path(
        self, path: str
    ) -> typing.Tuple[str, typing.Optional[os.stat_result]]:
        for directory in self.all_directories:
            full_path = os.path.realpath(os.path.join(directory, path))
            directory = os.path.realpath(directory)
            if os.path.commonprefix([full_path, directory]) != directory:
                continue

            try:
                stat_result = await aio_stat(full_path)
                return full_path, stat_result
            except FileNotFoundError:
                pass

        return "", None

    def file_response(
        self,
        full_path: PathLike,
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        req_headers = Headers(scope=scope)

        res = FileResponse(full_path, status_code=status_code, stat_result=stat_result)
        if self.is_not_modified(res.headers, req_headers):
            res = NotModifiedResponse(res.headers)
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