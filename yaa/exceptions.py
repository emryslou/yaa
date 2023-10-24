import http
import typing

__all__ = ("HttpException", "NotFoundException", "WebSocketException")


class HttpException(Exception):
    def __init__(
        self,
        status_code: int,
        detail: typing.Optional[str] = None,
        headers: typing.Optional[dict] = None,
    ) -> None:
        if detail is None:
            try:
                detail = http.HTTPStatus(status_code).phrase
            except ValueError:
                detail = "unknown http status code"

        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}

    def __repr__(self) -> str:
        klass_name = self.__class__.__name__
        return (
            f"{klass_name}(status_code={self.status_code}" f", detail={self.detail!r})"
        )


class NotFoundException(HttpException):
    def __init__(self, detail: typing.Optional[str] = None):
        super().__init__(status_code=404, detail=detail)  # pragma: no cover


class WebSocketException(Exception):
    def __init__(self, code: int, reason: typing.Optional[str] = None) -> None:
        self.code = code
        self.reason = reason or ""

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}(code={self.code!r}, reason={self.reason!r})"


class ParameterException(Exception):
    pass
