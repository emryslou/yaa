from yast.applications import Yast
from yast.responses import PlainTextResponse

app = Yast()

@app.route('/')
def home(req):
    return PlainTextResponse('home')