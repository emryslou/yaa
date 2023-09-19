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
from yast.types import Scope

NOT_MODIFIED_HEADERS = (
    "cache-control",
    "content-location",
    "date",
    "etag",
    "expires",
    "vary",
)


class StaticFiles(object):
    def __init__(self, *, directory, check_dir: bool = True) -> None:
        if check_dir:
            assert os.path.isdir(directory), f'Directory "{directory}" does not exists'
        self.directory = directory
        self.config_checked = False

    def __call__(self, scope: Scope):
        assert scope["type"] == "http"
        if scope["method"] not in ("GET", "HEAD"):
            return PlainTextResponse("Method Not Allowed", status_code=405)
        path = os.path.normpath(os.path.join(*scope["path"].split("/")))
        if path.startswith(".."):
            return PlainTextResponse("Not Found", status_code=404)

        path = os.path.join(self.directory, path)
        if self.config_checked:
            check_directory = None
        else:
            check_directory = self.directory
            self.config_checked = True

        return _StaticFilesResponser(scope, path, check_directory)


class _StaticFilesResponser(object):
    def __init__(self, scope, path, check_directory=None):
        self.scope = scope
        self.path = path
        self.check_directory = check_directory

    async def check_directory_configured_correctly(self):
        dir = self.check_directory
        try:
            stat_result = await aio_stat(dir)
        except FileNotFoundError:
            raise RuntimeError(f"Staticfiles directory {dir} does not found")

        if not (stat.S_ISDIR(stat_result.st_mode) or stat.S_ISLNK(stat_result.st_mode)):
            raise RuntimeError(f"Staticfiles directory {dir} is not a directory")

    def is_not_modified(self, stat_headers: typing.Dict[str, str]) -> bool:
        etag = stat_headers["etag"]
        last_modified = stat_headers["last-modified"]
        req_headers = Headers(scope=self.scope)
        if etag == req_headers.get("if-none-match"):
            return True
        if "if-modified-since" not in req_headers:
            return False
        last_req_time = req_headers["if-modified-since"]
        return parsedate(last_req_time) >= parsedate(last_modified)

    def not_modified_response(self, stat_headers: dict) -> Response:
        headers = {
            name: value
            for name, value in stat_headers.items()
            if name in NOT_MODIFIED_HEADERS
        }
        return Response(status_code=304, headers=headers)

    async def __call__(self, receive, send):
        if self.check_directory:
            await self.check_directory_configured_correctly()

        try:
            stat_result = await aio_stat(self.path)
        except FileNotFoundError:
            res = PlainTextResponse("Not Found", status_code=404)
        else:
            mode = stat_result.st_mode
            if not stat.S_ISREG(mode):
                res = PlainTextResponse("Not Found", status_code=404)
            else:
                stat_headers = FileResponse.get_stat_headers(stat_result)
                if self.is_not_modified(stat_headers):
                    res = self.not_modified_response(stat_headers)
                else:
                    res = FileResponse(
                        self.path, stat_result=stat_result, method=self.scope["method"]
                    )

        await res(receive, send)
