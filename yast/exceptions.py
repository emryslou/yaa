import http


class HttpException(Exception):
    def __init__(self, status_code: int, detail: str = None):
        if detail is None:
            detail = http.HTTPStatus(status_code).phrase

        self.status_code = status_code
        self.detail = detail
