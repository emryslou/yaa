from yast import Yast
from yast.responses import Response, FileResponse, RedirectResponse, HTMLResponse
from yast.requests import Request
from yast.staticfiles import StaticFiles
from yast.endpoints import HttpEndPoint, WebSocketEndpoint
from yast.routing import Path

app = Yast()


app.mount('/static', StaticFiles(directory='demo/static'))

@app.route('/')
def home(request: Request) -> Response: 
    return Response('<h1>Hello</h1>', media_type='text/html')

@app.route('/favicon.ico')
def fav(_):
    return RedirectResponse('/static/favicon.ico', 302)

class Demo(HttpEndPoint):
    def get(self, request: Request, **kwargs):
        return HTMLResponse('Demo')

app.add_route('/demo', route=Path('/', app=Demo))
"""
ReadMe:
python3 -m pip install 'uvicorn[standard]'
python3 -m uvicorn demo.main:app --port 5505
"""
