from yast import App, Response, Request, StaticFiles, FileResponse, RedirectResponse

app = App()
app.mount('/static', StaticFiles(directory='demo/static'))

@app.route('/')
def home(request: Request) -> Response: 
    return Response('<h1>Hello</h1>', media_type='text/html')

@app.route('/favicon.ico')
def fav(_):
    return RedirectResponse('/static/favicon.ico', 302)
"""
ReadMe:
python3 -m pip install 'uvicorn[standard]'
python3 -m uvicorn demo.main:app --port 5505
"""
