import graphene

from yast import Yast
from yast.graphql import GraphQLApp
from yast.responses import Response, FileResponse, RedirectResponse, HTMLResponse
from yast.requests import Request
from yast.staticfiles import StaticFiles
from yast.endpoints import HttpEndPoint, WebSocketEndpoint
from yast.routing import Route
from yast.websockets import WebSocket, WebSocketDisconnect
from yast.middlewares import SessionMiddleware, BaseHttpMiddleware


app = Yast()

app.add_middleware(SessionMiddleware, secret_key='test')

app.mount('/static', StaticFiles(directory='demo/static'))
app.mount('/docs', StaticFiles(directory='demo/docs'))

@app.route('/')
def home(request: Request) -> Response:
    html_content = (
        '<h1>Hello</h1>'
        '<input id="ws_host" value="localhost:5505/ws"/>'
        '<button id="send">send</button>'
        '<span id="receive_msg"></span>'
        '<script src="/static/js/ws.js?_no=125"></script>'
    )
    return Response(html_content, media_type='text/html')

@app.route('/favicon.ico')
def fav(_):
    return RedirectResponse('/static/favicon.ico', 302)

class Demo(HttpEndPoint):
    def get(self, request: Request, **kwargs):
        return HTMLResponse('Demo')

@app.ws_route('/ws')
class WsApp(WebSocketEndpoint):
    encoding = 'text'
    async def on_receive(self, data):
        await self.send('data received ' + data, 'text')

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
    import mkdocs


@app.on_event('cleanup')
def run_cleanup():
    print('cleanup')


class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value='stranger'))

    def resolve_hello(self, info, name):
        return 'Hello ' + name

schema = graphene.Schema(query=Query)

app.add_route('/graphql/query', GraphQLApp(schema=schema), methods=['GET', 'POST'])
"""
ReadMe:
python3 -m pip install 'uvicorn[standard]'
python3 -m uvicorn demo.main:app --port 5505
"""
