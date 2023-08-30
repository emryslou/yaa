import os
import stat

from aiofiles.os import stat as aio_stat

from yast.types import Scope
from yast import PlainTextResponse, FileResponse


class StaticFile(object):
    def __init__(self, *, path) -> None:
        self.path = path
    
    def __call__(self, scope: Scope):
        if scope['method'] not in ('GET', 'HEAD'):
            return PlainTextResponse('Method Not Allowed', status_code=405)
        
        return _StaticFileResponser(scope, self.path) 


class StaticFiles(object):
    def __init__(self, *, directory) -> None:
        self.directory = directory
        self.config_checked = False
    
    def __call__(self, scope: Scope):
        if scope['method'] not in ('GET', 'HEAD'):
            return PlainTextResponse('Method Not Allowed', status_code=405)
        
        path = os.path.normpath(os.path.join(*scope['path'].split('/')))
        if path.startswith('..'):
            return PlainTextResponse('Not Found', status_code=404)
        
        path = os.path.join(self.directory, path)
        if self.config_checked:
            check_directory = None
        else:
            check_directory = self.directory
            self.config_checked = True
        
        return _StaticFilesResponser(scope, path, check_directory)


class _StaticFileResponser(object):
    def __init__(self, scope, path):
        self.scope = scope
        self.path = path
    
    async def __call__(self, recevie, send):
        try:
            stat_result = await aio_stat(self.path)
        except FileNotFoundError:
            raise RuntimeError('StaticFile path "%s" does not found.' % self.path)
        else:
            mode =stat_result.st_mode
            if not stat.S_ISREG(mode):
                raise RuntimeError('StaticFile path "%s" is not a file.' % self.path)
            
            res = FileResponse(self.path, stat_result=stat_result)

            await res(recevie, send)

    

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
            raise RuntimeError('Staticfiles directory %s does not found' % dir)
       
        if not (stat.S_ISDIR(stat_result.st_mode) or stat.S_ISLNK(stat_result.st_mode)):
            raise RuntimeError('Staticfiles directory %s is not a directory' % dir)


    async def __call__(self, recevie, send):
        if self.check_directory:
            await self.check_directory_configured_correctly()
        
        try:
            stat_result = await aio_stat(self.path)
        except FileNotFoundError:
            res = PlainTextResponse('Not Found', status_code=404)
        else:
            mode =stat_result.st_mode
            if not stat.S_ISREG(mode):
                res = PlainTextResponse('Not Found', status_code=404)
            else:
                res = FileResponse(self.path, stat_result=stat_result)

        await res(recevie, send)