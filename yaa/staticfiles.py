"""
module: StaticFiles
title: StaticFiles
description:
    静态文件处理模块，例如: js, html, css, 图片等
author: emryslou@gmail.com
examples: test_staticfiles.py
exposes:
    - StaticFiles
    - NotModifiedResponse
"""

import os
import stat
import typing
from email.utils import parsedate
from pathlib import Path

import anyio

from yaa.datastructures import Headers
from yaa.exceptions import HttpException
from yaa.responses import FileResponse, RedirectResponse, Response
from yaa.types import Receive, Scope, Send

PathLike = typing.Union[str, "os.PathLike[str]"]


class NotModifiedResponse(Response):
    """文件未修改响应对象=304"""

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
    """静态文件
    用于需要直接下发的文件，例如：js，html，图片，视频等
    """

    def __init__(
        self,
        *,
        directory: typing.Optional[PathLike] = None,
        packages: typing.Optional[typing.List[str]] = None,
        html: bool = False,
        check_dir: bool = True,
    ) -> None:
        """初始化方法
        Args:
            directory: 静态文件存放根目录

            packages: 包列表，会扫描对应包名的同级别 `statics` 目录
                例如：['aa', 'bb']，假设 aa 所在目录 /some/packages/aa, bb 所在目录 /other/path/packages/bb
                则扫描目录分别为 /some/packages/aa/statics, /other/path/packages/statics

            html: 是否加载 html 默认为 `False`，
                html=False，如果访问目录或文件不存在或不可访问，则会响应 404
                html=True，如果访问路径为路径为目录，则会尝试加载对应目录的 index.html
                如果访问目录或文件不存在或不可访问， 则会尝试加载 404.html

            check_dir: 是否需要检测 `directory` 是否存在

        Returns:
            None

        Raises:
            RuntimeError: check_dir = True 且 directory 不是目录
        """
        self.directory = directory
        self.packages = packages
        self.all_directories = self.get_directories(directory, packages)
        self.html = html
        self.config_checked = False

        if check_dir and directory is not None and not Path(directory).is_dir():
            raise RuntimeError(f'Directory "{directory}" does not exists')

    def get_directories(
        self,
        directory: typing.Optional[PathLike] = None,
        packages: typing.Optional[typing.List[str]] = None,
    ) -> typing.List[PathLike]:
        directories = []

        if directory is not None:
            directories.append(directory)

        if packages is not None:
            from importlib import util

            for package in packages or []:
                if isinstance(package, tuple):
                    package, statics_dir = package
                else:
                    statics_dir = "statics"
                spec = util.find_spec(package)
                # package_directory = os.path.normpath(
                #     os.path.join(spec.submodule_search_locations[0], "..", statics_dir)  # type: ignore
                # )
                package_directory = (
                    Path(spec.submodule_search_locations[0])  # type: ignore[union-attr,index]
                    .joinpath("..", statics_dir)
                    .resolve()
                )
                assert package_directory.is_dir(), (
                    f"Directory `{statics_dir!r}` "
                    f"in package `{package}` could not be found\n"
                    f"{package_directory}"
                )

                directories.append(package_directory)
            # endfor
        # endif
        return directories

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"

        path = self.get_path(scope)
        res = await self.get_response(path, scope)
        await res(scope, receive=receive, send=send)

    def get_path(self, scope: Scope) -> Path:
        return Path(*scope["path"].split("/"))

    async def get_response(
        self,
        path: Path,
        scope: Scope,
    ) -> Response:
        if scope["method"] not in ("GET", "HEAD"):
            raise HttpException(status_code=405)

        if not self.config_checked:
            await self.check_config()
            self.config_checked = True

        try:
            full_path, stat_result = await anyio.to_thread.run_sync(
                self.lookup_path, path
            )
        except PermissionError:
            raise HttpException(status_code=401)
        except OSError:
            raise
        if stat_result and stat.S_ISREG(stat_result.st_mode):
            return self.file_response(full_path, stat_result, scope=scope)

        elif stat_result and stat.S_ISDIR(stat_result.st_mode) and self.html:
            index_path = path.joinpath("index.html")
            full_path, stat_result = await anyio.to_thread.run_sync(
                self.lookup_path, index_path
            )
            if stat_result is not None and stat.S_ISREG(stat_result.st_mode):
                if not scope["path"].endswith("/"):
                    from yaa.datastructures import URL

                    url = URL(scope=scope)
                    url = url.replace(path=url.path + "/")
                    return RedirectResponse(url)
                # endif
                return self.file_response(full_path, stat_result, scope)
            # endif
        # endif
        if self.html:
            full_path, stat_result = await anyio.to_thread.run_sync(
                self.lookup_path, "404.html"
            )
            if stat_result and stat.S_ISREG(stat_result.st_mode):
                return FileResponse(full_path, stat_result=stat_result, status_code=404)
        raise HttpException(status_code=404)

    def lookup_path(
        self, path: Path
    ) -> typing.Tuple[Path, typing.Optional[os.stat_result]]:
        for directory in self.all_directories:
            original_path = Path(directory).joinpath(path)
            full_path = original_path.resolve()
            directory = Path(directory).resolve()
            try:
                stat_result = os.lstat(original_path)
                full_path.relative_to(directory)
                return full_path, stat_result
            except ValueError:
                if stat.S_ISLNK(stat_result.st_mode):
                    stat_result = os.lstat(full_path)
                    return full_path, stat_result
            except (FileNotFoundError, NotADirectoryError):
                continue

        return Path(), None

    def file_response(
        self,
        full_path: PathLike,
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        req_headers = Headers(scope=scope)

        res = FileResponse(
            full_path, status_code=status_code, stat_result=stat_result
        )  # type: Response
        if self.is_not_modified(res.headers, req_headers):
            res = NotModifiedResponse(res.headers)  # type: ignore
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
            stat_result = await anyio.to_thread.run_sync(os.stat, self.directory)
        except FileNotFoundError:
            raise RuntimeError(
                f"StaticFile directory `{self.directory}` does not exists"
            )

        if not (stat.S_ISDIR(stat_result.st_mode) or stat.S_ISLNK(stat_result.st_mode)):
            raise RuntimeError(
                f"StaticFile directory `{self.directory}` is not a directory"
            )
