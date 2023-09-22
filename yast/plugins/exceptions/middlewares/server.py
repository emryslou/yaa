import asyncio
import functools
import traceback
import typing

from yast.concurrency import run_in_threadpool
from yast.requests import Request
from yast.responses import HTMLResponse, PlainTextResponse, Response
from yast.types import ASGIApp, ASGIInstance, Message, Receive, Scope, Send


def req_method_content_length_eq_0(headers: list) -> list:
    import warnings

    warnings.warn("Code Opt: Too ugly, need to find some better way to solve it")
    raw_headers = headers
    headers = []

    for header_name, header_value in raw_headers:
        if b"content-length" == header_name:
            header_value = b"0"
        headers.append((header_name, header_value))

    return headers


class ServerErrorMiddleware(object):
    def __init__(
        self, app: ASGIApp, handler: typing.Callable = None, debug: bool = False
    ) -> None:
        self.app = app
        self.handler = handler
        self.debug = debug

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive=receive, send=send)
        else:
            await self.asgi(scope=scope, receive=receive, send=send)

    async def asgi(self, receive: Receive, send: Send, scope: Scope) -> None:
        res_start = False

        async def _send(msg: Message):
            nonlocal res_start, send

            if msg["type"] == "http.response.start":
                res_start = True
                if scope["method"].upper() == "HEAD":
                    msg["headers"] = req_method_content_length_eq_0(
                        msg.get("headers", [])
                    )

            await send(msg)

        try:
            await self.app(scope, receive, _send)
        except Exception as exc:
            if not res_start:
                req = Request(scope=scope)
                if self.debug:
                    res = self.debug_response(req, exc)
                elif self.handler is None:
                    res = self.error_response(req, exc)
                else:
                    if asyncio.iscoroutinefunction(self.handler):
                        res = await self.handler(req, exc)
                    else:
                        res = await run_in_threadpool(self.handler, req, exc)
                # endif
                await res(scope, receive, send)
            # endif
            raise exc from None

    def debug_response(self, req: Request, exc: Exception) -> Response:
        accept = req.headers.get("accept", "")
        debug_gen = DebuggerGenerator(exc)

        if "text/html" in accept:
            content = debug_gen.html()
            return HTMLResponse(content, status_code=500)

        content = debug_gen.text()
        return PlainTextResponse(content, status_code=500)

    def error_response(self, req: Request, exc: Exception) -> Response:
        return PlainTextResponse("Internal Server Error", status_code=500)


class DebuggerGenerator(object):
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.traceback_obj = traceback.TracebackException.from_exception(
            exc, capture_locals=True
        )
        self.error = f"{self.traceback_obj.exc_type.__name__}" f": {self.traceback_obj}"

    def gen_frame_html(self, frame: traceback.FrameSummary) -> str:
        values = {
            "frame_filename": frame.filename,
            "frame_lineno": frame.lineno,
            "frame_name": frame.name,
            "frame_line": frame.line,
        }
        return FRAME_TEMPLATE.format(**values)

    def html(self) -> str:
        html = "".join(
            [self.gen_frame_html(frame) for frame in self.traceback_obj.stack]
        )
        values = {"style": STYLES, "error": self.error, "ext_html": html}
        return TEMPLATE.format(**values)

    def text(self) -> str:
        return "".join(traceback.format_tb(self.exc.__traceback__))


STYLES = """\
    .traceback-container {border: 1px solid #038BB8;}
    .traceback-title {background-color: #038BB8;color: lemonchiffon;padding: 12px;font-size: 20px;margin-top: 0px;}
    .traceback-content {padding: 5px 0px 20px 20px;}
    .frame-line {font-weight: unset;padding: 10px 10px 10px 20px;background-color: #E4F4FD;
    margin-left: 10px;margin-right: 10px;font: #394D54;color: #191f21;font-size: 17px;border: 1px solid #c7dce8;}
"""
TEMPLATE = """
    <style type='text/css'>{style}</style>
    <title>Starlette Debugger</title>
    <h1>500 Server Error</h1>
    <h2>{error}</h2>
    <div class='traceback-container'>
    <p class='traceback-title'>Traceback</p>
    <div class='traceback-content'>{ext_html}</div>
    </div>
"""
FRAME_TEMPLATE = """
    <p>
    File <span class='debug-filename'>`{frame_filename}`</span>,
    line <i>{frame_lineno}</i>,
    in <b>{frame_name}</b>
    <p class='frame-line'>{frame_line}</p>
    </p>
"""
