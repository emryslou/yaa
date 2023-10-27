import graphene
import json

from yaa import Yaa
from yaa.responses import Response, FileResponse, RedirectResponse, HTMLResponse, PlainTextResponse, JSONResponse
from yaa.requests import Request
from yaa.staticfiles import StaticFiles
from yaa.endpoints import HttpEndPoint, WebSocketEndpoint
from yaa.routing import Route
from yaa.websockets import WebSocket, WebSocketDisconnect
from yaa.middlewares import BaseHttpMiddleware
from yaa.plugins.template import get_templates


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

@app.route('/home/{user:str}')
async def home(request: Request) -> Response:
    from random import randint
    await request.send_push_promise('/static/js/ws.js')
    await request.send_push_promise('/static/css/ws_css.css')
    res = get_templates().response('home.html', context={
        'request': request,
        'greeting': 'WebSocket',
        'ws_path': '/ws/{}'.format(request.path_params['user']),
        'js_version': randint(0, 1000),
        'user': request.path_params['user'],
    })
    return res
    

@app.route('/favicon.ico')
def fav(_):
    return FileResponse('demo/static/favicon.ico')

class Demo(HttpEndPoint):
    def get(self, request: Request, **kwargs):
        return HTMLResponse('Demo')

@app.ws_route('/ws/{user:str}')
class WsApp(WebSocketEndpoint):
    encoding = 'text'
    async def on_receive(self, data):
        try:
            msg_body = json.loads(data)
        except Exception as exc:
            print('exc:', exc)
            msg_body = {}
        if msg_body:
            if msg_body['to_user'] == '':
                await self.ws.notify_others('`{}` from user [{}]'.format(msg_body['msg'], self.ws.path_params['user']))
            else:
                await self.ws._agent.send_to(
                    msg_body['to_user'],
                    'send_text',
                    data='`{}` from user [{}]'.format(msg_body['msg'], self.ws.path_params['user'])
                )

    async def on_connect(self):
        await super().on_connect()
        await self.send('login, quid:' + self.ws.quid, 'text')
        data = 'user[{}:{}] on line'.format(self.ws.path_params['user'], self.ws.quid)
        await self.ws.notify_others(data)
    
    async def on_disconnect(self, close_code):
        data = 'user[{}:{}] off line'.format(self.ws.path_params['user'], self.ws.quid)
        await self.ws.notify_others(data)


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

import cProfile, pstats, io
from pstats import SortKey

pr = cProfile.Profile()

@app.on_event('startup')
def run_startup():
    pr.enable()

@app.on_event('shutdown')
def run_cleanup():
    pr.disable()
    s = io.StringIO()
    sort_by = SortKey.CUMULATIVE
    ps = pstats.Stats(pr, stream=s).sort_stats(sort_by)
    ps.print_stats(10)
    print(s.getvalue())


"""
ReadMe:
python3 -m pip install 'uvicorn[standard]'
python3 -m uvicorn demo.main:app --port 5505
"""
