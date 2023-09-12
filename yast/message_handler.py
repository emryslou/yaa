import enum

from yast.types import Message


class MessageType(enum.Enum):
    HttpResponseStart = "http.response.start"
    HttpResponseBody = "http.response.body"

    def __str__(self):
        return self.value


class MessageHandler(object):
    def __init__(self):
        self.handlers = {}

    def on_type(self, msg_type: str):
        _ = MessageType(msg_type)

        def decorator(func):
            self.handlers[msg_type] = func
            return func

        return decorator

    async def _do_nothing(self, message: Message):
        pass

    async def __call__(self, message: Message):
        assert "type" in message
        await self.handlers.get(message["type"], [self._do_nothing])(message)
