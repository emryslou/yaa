import traceback
import html

from yast.types import ASGIApp, ASGIInstance, Scope, Recevie, Send
from yast import Headers, PlainTextResponse, HTMLResponse


class DebugMiddleware(object):
    def __init__(self, app: ASGIApp):
        self.app = app
    
    def __call__(self, scope: Scope):
        return _DebuggerResponser(self.app, scope)


class _DebuggerResponser(object):
    def __init__(self, app: ASGIApp, scope: Scope):               
        self.scope = scope
        self.asgi_instance = app(scope)
        self.response_started = False

    async def __call__(self, receive, send):
        self.raw_send = send
        try:
            await self.asgi_instance(receive, self.send)
        except:
            if self.response_started:
                raise
            headers = Headers(self.scope.get('headers', []))
            accept = headers.get('accept', '')
            if 'text/html' in accept:
                exc_html = html.escape(traceback.format_exc())
                content = f'<html><body><h1>500 Server Error</h1><pre>{exc_html}</pre></body></html>'
                res = HTMLResponse(content, status_code=500)
            else:
                content = traceback.format_exc()
                res = PlainTextResponse(content, status_code=500)
        
            await res(Recevie, send)
    
    async def send(self, message):
        if message['type'] == 'http.response.start':
            self.response_started = True
        await self.raw_send(message)

                                       