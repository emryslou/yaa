import tempfile
import typing

from yast.concurrency import run_in_threadpool


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


class FormData(typing.Mapping[str, FormValue]):
    def __init__(
        self,
        form: typing.Union["FormData", typing.Mapping[str, FormValue]] = None,
        items: typing.List[FormValue] = None,
    ) -> None:
        _items = []
        if form is not None:
            assert items is None, "Cannot set both `form` and `items`"
            if isinstance(form, FormData):
                _items = list(form.multi_items())
            else:
                _items = list(form.items())
        elif items is not None:
            _items = list(items)

        self._dict = {k: v for k, v in _items}
        self._list = _items

    def getlist(self, key: typing.Any) -> typing.List[FormValue]:
        return [_v for _k, _v in self._list if _k == key]

    def keys(self) -> typing.List[str]:
        return list(self._dict.keys())

    def values(self) -> typing.List[typing.Tuple[str, FormValue]]:
        return list(self._dict.values())

    def items(self) -> typing.List[typing.Tuple[str, FormValue]]:
        return list(self._dict.items())

    def multi_items(self) -> typing.List[typing.Tuple[str, FormValue]]:
        return list(self._list)

    def get(self, key: typing.Any, default: typing.Any = None) -> typing.Any:
        if key in self._dict:
            return self._dict[key]
        return default

    def __getitem__(self, key: typing.Any) -> FormValue:
        return self._dict[key]

    def __contains__(self, key: typing.Any) -> bool:
        return key in self._dict

    def __iter__(self) -> typing.Iterator[typing.Any]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._dict)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, FormData):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self) -> str:
        items = self.multi_items()
        return f"{self.__class__.__name__}(items={repr(items)})"
