import graphene

from yast import Yast
from yast.responses import Response, FileResponse, RedirectResponse, HTMLResponse
from yast.requests import Request
from yast.staticfiles import StaticFiles
from yast.endpoints import HttpEndPoint, WebSocketEndpoint
from yast.routing import Route
from yast.websockets import WebSocket, WebSocketDisconnect
from yast.middlewares import BaseHttpMiddleware
from yast.plugins.template import templates


class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value='stranger'))

    def resolve_hello(self, info, name):
        return 'Hello ' + name

app = Yast(
    debug=True,
    plugins = {
        'session': {
            "secret_key": 'test'
        },
        'template': {
            'template_directory': 'demo/templates'
        },
        'graphql': {
            'routes': [{
                'path': '/graphql/query',
                'schema': graphene.Schema(query=Query),
                'methods': ['GET', 'POST'],
            }]
        }
    }
)


app.mount('/static', StaticFiles(directory='demo/static'))
app.mount('/docs', StaticFiles(directory='demo/docs', html=True))

@app.route('/')
def home(request: Request) -> Response:
    return templates.response('home.html', request=request, context={
        'greeting': 'template',
        'ws_host': 'localhost:5505/ws',
        'js_version': '127'
    })
    

@app.route('/favicon.ico')
def fav(_):
    return FileResponse('/static/favicon.ico')

class Demo(HttpEndPoint):
    def get(self, request: Request, **kwargs):
        return HTMLResponse('Demo')

@app.ws_route('/ws')
class WsApp(WebSocketEndpoint):
    encoding = 'text'
    async def on_receive(self, data):
        await self.send('data received ' + data, 'text')

@app.route('/aa')
def aa(req):
    raise RuntimeError('AAA')

class YaWs(object):
    def __init__(self, scope):
        self.scope = scope
    
    async def __call__(self, receive, send):
        ws = WebSocket(self.scope, receive, send)
        await ws.accept()
        await ws.send_text('Hello, Ws')
        while True:
            try:
                data = await ws.receive_text()
                await ws.send_text('msg received, is:' + data)
            except WebSocketDisconnect:
                await ws.close()
                break

app.add_route_ws('/yaws', route=YaWs)
app.add_route('/demo', route=Route('/', endpoint=Demo))

@app.on_event('startup')
def run_startup():
    print('startup')


@app.on_event('shutdown')
def run_cleanup():
    print('cleanup')


"""
ReadMe:
python3 -m pip install 'uvicorn[standard]'
python3 -m uvicorn demo.main:app --port 5505
"""
