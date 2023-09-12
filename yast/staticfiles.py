import os
import stat

from aiofiles.os import stat as aio_stat

from yast.responses import FileResponse, PlainTextResponse
from yast.types import Scope


class StaticFiles(object):
    def __init__(self, *, directory, check_dir: bool = True) -> None:
        if check_dir:
            assert os.path.isdir(directory), 'Directory "%s" does not exists' % (
                directory
            )
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
            raise RuntimeError("Staticfiles directory %s does not found" % dir)

        if not (stat.S_ISDIR(stat_result.st_mode) or stat.S_ISLNK(stat_result.st_mode)):
            raise RuntimeError("Staticfiles directory %s is not a directory" % dir)

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
                res = FileResponse(
                    self.path, stat_result=stat_result, method=self.scope["method"]
                )

        await res(receive, send)
