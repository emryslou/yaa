import tempfile
import typing

from yaa.concurrency import run_in_threadpool

from .headers import Headers
from .types import ImmutableMultiDict


class UploadFile(object):
    spool_max_size = 1024 * 1024
    headers: "Headers"

    def __init__(
        self,
        filename: str,
        file: typing.Optional[typing.IO] = None,
        content_type: str = "",
        *,
        headers: Headers = Headers(),
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        if file is None:
            file = tempfile.SpooledTemporaryFile(max_size=self.spool_max_size)
        self.file = file
        self.headers = headers

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


class FormData(ImmutableMultiDict):
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
