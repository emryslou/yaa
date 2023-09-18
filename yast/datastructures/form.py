import tempfile
import typing

from yast.concurrency import run_in_threadpool

from .types import ImmutableMultiDict


class UploadFile(object):
    def __init__(self, filename: str, file: typing.IO = None) -> None:
        self.filename = filename
        if file is None:
            file = tempfile.SpooledTemporaryFile()
        self.file = file

    async def write(self, data: typing.Union[bytes, str]) -> None:
        await run_in_threadpool(self.file.write, data)

    async def read(self, size: int = None) -> typing.Union[bytes, str]:
        return await run_in_threadpool(self.file.read, size)

    async def seek(self, offset: int) -> None:
        await run_in_threadpool(self.file.seek, offset)

    async def close(self) -> None:
        await run_in_threadpool(self.file.close)


FormValue = typing.Union[str, "FormValue"]


class FormData(ImmutableMultiDict):
    def __init__(
        self,
        value: typing.Union[
            "FormData",
            typing.Mapping[str, FormValue],
            typing.List[typing.Tuple[str, FormValue]],
        ] = None,
        **kwargs: typing.Any,
    ) -> None:
        if kwargs:
            value = kwargs.pop("form", value)
            value = kwargs.pop("items", value)
            assert not kwargs, "Unknown parameter"

        super().__init__(value)
