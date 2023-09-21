import enum


class EventType(enum.Enum):
    STARTUP: str = "startup"
    SHUTDOWN: str = "shutdown"

    def __str__(self) -> str:
        return self.value

    @property
    def lifespan(self) -> str:
        return f"lifespan.{self.value}"

    @property
    def complete(self) -> str:
        return f"{self.lifespan}.complete"

    @staticmethod
    def get_by_lifespan(lifespan: str) -> "EventType":
        return EventType(lifespan.replace("lifespan.", ""))
