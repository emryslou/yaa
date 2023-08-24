from yast import AsgiApp, Response, Request

@AsgiApp
def app(request: Request) -> Response: 
    return Response('<h1>Hello</h1>', media_type='text/html')

"""
ReadMe:
python3 -m pip install 'uvicorn[standard]'
python3 -m uvicorn demo.main:app --port 5505
"""
