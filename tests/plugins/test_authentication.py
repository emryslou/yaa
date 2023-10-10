import base64
import binascii

import pytest

from yaa.applications import Yaa
from yaa.plugins.authentication.base import SimpleUser, requires
from yaa.plugins.authentication.middlewares import (
    AuthCredentials,
    AuthenticationMiddleware,
    AuthenticationBackend,
    AuthenticationError,
)
from yaa.endpoints import HttpEndPoint
from yaa.requests import Request
from yaa.responses import JSONResponse
from yaa.websockets import WebSocketDisconnect


class BasicAuth(AuthenticationBackend):
    async def authenticate(self, request):
        if "Authorization" not in request.headers:
            return None

        auth = request.headers["Authorization"]
        try:
            scheme, credentials = auth.split()
            decoded = base64.b64decode(credentials).decode("ascii")
        except (ValueError, UnicodeDecodeError, binascii.Error):
            raise AuthenticationError("Invalid basic auth credentials")

        username, _, password = decoded.partition(":")
        return AuthCredentials(["authenticated"]), SimpleUser(username)


app = Yaa(
    plugins={
        "authentication": {"middlewares": {"authentication": dict(backend=BasicAuth())}}
    }
)


@app.route("/")
def homepage(request):
    return JSONResponse(
        {
            "authenticated": request.user.is_authenticated,
            "user": request.user.display_name,
        }
    )


@app.route("/dashboard")
@requires("authenticated")
async def dashboard(request):
    return JSONResponse(
        {
            "authenticated": request.user.is_authenticated,
            "user": request.user.display_name,
        }
    )


@app.route("/admin")
@requires("authenticated", redirect="homepage")
async def admin(request):
    return JSONResponse(
        {
            "authenticated": request.user.is_authenticated,
            "user": request.user.display_name,
        }
    )


@app.route("/dashboard/sync")
@requires("authenticated")
def dashboard_sync(request):
    return JSONResponse(
        {
            "authenticated": request.user.is_authenticated,
            "user": request.user.display_name,
        }
    )


@app.route("/dashboard/class")
class Dashboard(HttpEndPoint):
    @requires("authenticated")
    def get(self, request):
        return JSONResponse(
            {
                "authenticated": request.user.is_authenticated,
                "user": request.user.display_name,
            }
        )


@app.route("/admin/sync")
@requires("authenticated", redirect="homepage")
def admin_sync(request):
    return JSONResponse(
        {
            "authenticated": request.user.is_authenticated,
            "user": request.user.display_name,
        }
    )


@app.ws_route("/ws")
@requires("authenticated")
async def websocket_endpoint(websocket):
    await websocket.accept()
    await websocket.send_json(
        {
            "authenticated": websocket.user.is_authenticated,
            "user": websocket.user.display_name,
        }
    )


def async_inject_decorator(**kwargs):
    def wrapper(endpoint):
        async def app(request):
            return await endpoint(request=request, **kwargs)

        return app

    return wrapper


@app.route("/dashboard/decorated")
@async_inject_decorator(additional="payload")
@requires("authenticated")
async def decorated_sync(request, additional):
    return JSONResponse(
        {
            "authenticated": request.user.is_authenticated,
            "user": request.user.display_name,
            "additional": additional,
        }
    )


def sync_inject_decorator(**kwargs):
    def wrapper(endpoint):
        def app(request):
            import asyncio

            return asyncio.run(endpoint(request=request, **kwargs))

        return app

    return wrapper


@app.route("/dashboard/decorated/sync")
@sync_inject_decorator(additional="payload")
@requires("authenticated")
def decorated_sync(request, additional):
    return JSONResponse(
        {
            "authenticated": request.user.is_authenticated,
            "user": request.user.display_name,
            "additional": additional,
        }
    )


def ws_inject_decorator(**kwargs):
    def wrapper(endpoint):
        def app(websocket):
            return endpoint(websocket=websocket, **kwargs)

        return app

    return wrapper


@app.ws_route("/ws/decorated")
@ws_inject_decorator(additional="payload")
@requires("authenticated")
async def websocket_endpoint(websocket, additional):
    await websocket.accept()
    await websocket.send_json(
        {
            "authenticated": websocket.user.is_authenticated,
            "user": websocket.user.display_name,
            "additional": additional,
        }
    )


def test_invalid_decorator_usage():
    with pytest.raises(Exception):

        @requires("authenticated")
        def foo():
            pass  # pragma: nocover


def test_user_interface(client_factory):
    with client_factory(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"authenticated": False, "user": ""}

        response = client.get("/", auth=("eml", "example"))
        assert response.status_code == 200
        assert response.json() == {"authenticated": True, "user": "eml"}


def test_authentication_required(client_factory):
    with client_factory(app) as client:
        response = client.get("/dashboard")
        assert response.status_code == 403

        response = client.get("/dashboard", auth=("eml", "example"))
        assert response.status_code == 200
        assert response.json() == {"authenticated": True, "user": "eml"}

        response = client.get("/dashboard/sync")
        assert response.status_code == 403

        response = client.get("/dashboard/sync", auth=("eml", "example"))
        assert response.status_code == 200
        assert response.json() == {"authenticated": True, "user": "eml"}

        response = client.get("/dashboard/class")
        assert response.status_code == 403

        response = client.get("/dashboard/class", auth=("eml", "example"))
        assert response.status_code == 200
        assert response.json() == {"authenticated": True, "user": "eml"}

        response = client.get("/dashboard/decorated", auth=("eml", "example"))
        assert response.status_code == 200
        assert response.json() == {
            "authenticated": True,
            "user": "eml",
            "additional": "payload",
        }

        response = client.get("/dashboard/decorated")
        assert response.status_code == 403

        response = client.get("/dashboard/decorated/sync", auth=("eml", "example"))
        assert response.status_code == 200
        assert response.json() == {
            "authenticated": True,
            "user": "eml",
            "additional": "payload",
        }

        response = client.get("/dashboard/decorated/sync")
        assert response.status_code == 403

        response = client.get("/dashboard", headers={"Authorization": "basic foobar"})
        assert response.status_code == 400
        assert response.text == "Invalid basic auth credentials"


def test_websocket_authentication_required(client_factory):
    with client_factory(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.wsconnect("/ws"):
                pass

        with pytest.raises(WebSocketDisconnect):
            headers = {"Authorization": "basic foobar"}
            with client.wsconnect("/ws", headers=headers):
                pass

        with client.wsconnect("/ws", auth=("eml", "example")) as websocket:
            data = websocket.receive_json()
            assert data == {"authenticated": True, "user": "eml"}

        with pytest.raises(WebSocketDisconnect):
            with client.wsconnect("/ws/decorated"):
                pass

        with pytest.raises(WebSocketDisconnect):
            headers = {"Authorization": "basic foobar"}
            with client.wsconnect("/ws/decorated", headers=headers):
                pass

        with client.wsconnect("/ws/decorated", auth=("eml", "example")) as websocket:
            data = websocket.receive_json()
            assert data == {
                "authenticated": True,
                "user": "eml",
                "additional": "payload",
            }


def test_authentication_redirect(client_factory):
    with client_factory(app) as client:
        response = client.get("/admin")
        assert response.status_code == 200
        assert response.url == "http://testserver/"

        response = client.get("/admin", auth=("eml", "example"))
        assert response.status_code == 200
        assert response.json() == {"authenticated": True, "user": "eml"}

        response = client.get("/admin/sync")
        assert response.status_code == 200
        assert response.url == "http://testserver/"

        response = client.get("/admin/sync", auth=("eml", "example"))
        assert response.status_code == 200
        assert response.json() == {"authenticated": True, "user": "eml"}


def on_auth_error(request: Request, exc: Exception):
    return JSONResponse({"error": str(exc)}, status_code=401)


other_app = Yaa(
    plugins={
        "authentication": {
            "middlewares": {
                "authentication": dict(backend=BasicAuth(), on_error=on_auth_error)
            }
        }
    }
)


@other_app.route("/control-panel")
@requires("authenticated")
def control_panel(request):
    return JSONResponse(
        {
            "authenticated": request.user.is_authenticated,
            "user": request.user.display_name,
        }
    )


def test_custom_on_error(client_factory):
    with client_factory(other_app) as client:
        response = client.get("/control-panel", auth=("eml", "example"))
        assert response.status_code == 200
        assert response.json() == {"authenticated": True, "user": "eml"}

        response = client.get(
            "/control-panel", headers={"Authorization": "basic foobar"}
        )
        assert response.status_code == 401
        assert response.json() == {"error": "Invalid basic auth credentials"}
