import typing

from yaa.concurrency import run_in_threadpool

from .headers import Headers
from .types import ImmutableMultiDict


class UploadFile(object):
    # spool_max_size = 1024 * 1024
    # headers: "Headers"

    def __init__(
        self,
        file: typing.BinaryIO,
        *,
        filename: typing.Optional[str] = None,
        headers: typing.Optional[Headers] = None,
    ) -> None:
        self.filename = filename
        self.file = file
        self.headers = headers or Headers()

    @property
    def content_type(self) -> typing.Optional[str]:
        return self.headers.get("content-type", None)

    @property
    def _in_memory(self) -> bool:
        rolled_to_disk = getattr(self.file, "_rolled", True)
        return not rolled_to_disk

    async def write(self, data: typing.Union[bytes, str]) -> None:
        if self._in_memory:
            self.file.write(data)  # type: ignore[arg-type]
        else:
            await run_in_threadpool(self.file.write, data)  # type: ignore[arg-type]

    async def read(self, size: int = -1) -> typing.Union[bytes, str]:
        if self._in_memory:
            return self.file.read(size)
        return await run_in_threadpool(self.file.read, size)

    async def seek(self, offset: int) -> None:
        if self._in_memory:
            self.file.seek(offset)
        else:
            await run_in_threadpool(self.file.seek, offset)

    async def close(self) -> None:
        if self._in_memory:
            self.file.close()
        else:
            await run_in_threadpool(self.file.close)


FormValue = typing.Union[str, "FormValue"]  # type: ignore[misc]


class FormData(ImmutableMultiDict[str, typing.Union[UploadFile, str]]):
    def __init__(
        self,
        value: typing.Optional[
            typing.Union[
                "FormData",
                typing.Mapping[str, FormValue],
                typing.List[typing.Tuple[str, FormValue]],
            ]
        ] = None,
        **kwargs: typing.Any,
    ) -> None:
        if kwargs:
            value = kwargs.pop("form", value)
            value = kwargs.pop("items", value)
            assert not kwargs, "Unknown parameter"

        super().__init__(value)  # type: ignore[arg-type]

    async def close(self) -> None:
        for _, value in self.multi_items():
            if isinstance(value, UploadFile):
                await value.close()
