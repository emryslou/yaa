import traceback
import html

from yast.datastructures import Headers
from yast.requests import Request
from yast.responses import PlainTextResponse, HTMLResponse
from yast.types import ASGIApp, ASGIInstance, Scope, Recevie, Send

def get_debug_response(request:Request, exc):
    accept = request.headers.get('accept', '')
    content = ''.join(traceback.format_tb(exc.__traceback__))
    if 'text/html' in accept:
        content = html.escape(content)
        content = (
            '<html><body><h1>500 Server Error</h1>'
            f'<pre>{content}</pre></body></html>'
        )
        return HTMLResponse(content, status_code=500)
    else:
        return PlainTextResponse(content, status_code=500)


class DebugMiddleware(object):
    def __init__(self, app: ASGIApp):
        self.app = app
    
    def __call__(self, scope: Scope):
        if scope['type'] != 'http':
            return self.app(scope)
            
        return _DebuggerResponser(self.app, scope)


class _DebuggerResponser(object):
    def __init__(self, app: ASGIApp, scope: Scope):               
        self.scope = scope
        self.app = app
        self.response_started = False

    async def __call__(self, receive, send):
        self.raw_send = send
        try:
            await self.app(self.scope)(receive, self.send)
        except BaseException as exc:
            if not self.response_started:
                req = Request(self.scope, receive)
                res = get_debug_response(req, exc)
                await res(receive, send)
            raise exc from None
    
    async def send(self, message):
        if message['type'] == 'http.response.start':
            self.response_started = True
        await self.raw_send(message)

                                       