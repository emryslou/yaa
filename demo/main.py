import graphene

from yaa import Yaa
from yaa.responses import Response, FileResponse, RedirectResponse, HTMLResponse, PlainTextResponse, JSONResponse
from yaa.requests import Request
from yaa.staticfiles import StaticFiles
from yaa.endpoints import HttpEndPoint, WebSocketEndpoint
from yaa.routing import Route
from yaa.websockets import WebSocket, WebSocketDisconnect
from yaa.middlewares import BaseHttpMiddleware
from yaa.plugins.template import templates


class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value='stranger'))

    def resolve_hello(self, info, name):
        return 'Hello ' + name

app = Yaa(
    debug=False,
    plugins = {
        'session': {
            "secret_key": 'test'
        },
        'template': {
            'directory': 'demo/templates'
        },
        'database': {
            "enable_db_types": [{"db_type": "mysql"}],
            'middlewares': {
                'database': dict(database_url='mysql+pymysql://root:password@localhost:3306/information_schema')
            }
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
# app.mount('/docs', StaticFiles(directory='../.temp/docs', html=True))

@app.route('/')
async def links(req) -> Response:
    links = [
        str(r)
        for r in app.routes
    ]

    links_text = ',\n'.join(links)

    return PlainTextResponse(links_text)

@app.route('/home')
async def home(request: Request) -> Response:
    from random import randint
    await request.send_push_promise('/static/js/ws.js')
    await request.send_push_promise('/static/css/ws_css.css')
    res = templates.response('home.html', request=request, context={
        'greeting': 'template',
        'ws_host': 'localhost:5505/ws',
        'js_version': randint(0, 1000)
    })
    return res
    

@app.route('/favicon.ico')
def fav(_):
    return FileResponse('demo/static/favicon.ico')

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

@app.route('/db')
async def db(req):
    session = req.database
    conn = await session.acquire_connection()
    cursor = await conn.cursor()
    try:
        await cursor.execute('show tables', ())
        result = cursor.fetchone()
        row = result.result()
        return JSONResponse(row)
    except BaseException:
        return JSONResponse(content={'errr'}, status_code=500)
    finally:
        await cursor.close()
        await session.release_connection()

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
