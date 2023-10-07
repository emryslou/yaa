from yaa.applications import Yaa
from yaa.responses import PlainTextResponse

app = Yaa()

@app.route('/')
def home(req):
    return PlainTextResponse('home')