import itertools
import typing
from typing import Iterator


class ImmutableMultiDict(typing.Mapping):
    def __init__(
        self,
        value: typing.Union[
            "ImmutableMultiDict",
            typing.Mapping,
            typing.List[typing.Tuple[typing.Any, typing.Any]],
        ] = None,
    ) -> None:
        if value is None:
            _items = []
        elif hasattr(value, "multi_items"):
            value = typing.cast(ImmutableMultiDict, value)
            _items = list(value.multi_items())
        elif hasattr(value, "items"):
            value = typing.cast(typing.Mapping, value)
            _items = list(value.items())
        else:
            value = typing.cast(
                typing.List[typing.Tuple[typing.Any, typing.Any]], value
            )
            _items = list(value)

        self._dict = {k: v for k, v in _items}
        self._list = _items

    def getlist(self, key: typing.Any) -> typing.List[str]:
        return [item_value for item_key, item_value in self._list if item_key == key]

    def keys(self) -> typing.KeysView:
        return self._dict.keys()

    def values(self) -> typing.ValuesView:
        return self._dict.values()

    def items(self) -> typing.ItemsView:
        return self._dict.items()

    def multi_items(self) -> typing.List[typing.Tuple[str, str]]:
        return list(self._list)

    def get(self, key: typing.Any, default: typing.Any = None) -> typing.Any:
        if key in self._dict:
            return self._dict[key]
        return default

    def __getitem__(self, key: typing.Any) -> str:
        return self._dict[key]

    def __contains__(self, key: typing.Any) -> bool:
        return key in self._dict

    def __iter__(self) -> typing.Iterator[typing.Any]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._dict)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self) -> str:
        items = self.multi_items()
        return f"{self.__class__.__name__}({repr(items)})"


class MultiDict(ImmutableMultiDict):
    def __setitem__(self, key: typing.Any, value: typing.Any) -> None:
        self.setlist(key, [value])

    def __delitem__(self, key: typing.Any) -> None:
        self._list = [(k, v) for k, v in self._list if k != key]
        del self._dict[key]

    def pop(self, key: typing.Any, default: typing.Any = None) -> typing.Any:
        self._list = [(k, v) for k, v in self._list if k != key]
        return self._dict.pop(key, default)

    def popitem(self) -> typing.Tuple:
        key, value = self._dict.popitem()
        self._list = [(k, v) for k, v in self._list if k != key]
        return key, value

    def poplist(self, key: typing.Any) -> typing.List:
        values = [v for k, v in self._list if k == key]
        self.pop(key)
        return values

    def clear(self) -> None:
        self._dict.clear()
        self._list.clear()

    def setdefault(self, key: typing.Any, default: typing.Any = None) -> typing.Any:
        if key not in self:
            self._dict[key] = default
            self._list.append((key, default))
        return self[key]

    def setlist(self, key: typing.Any, values: typing.List) -> None:
        self.pop(key, None)
        if not values:
            values = []
        else:
            self._dict[key] = values[-1]
        self._list.extend(((key, value) for value in values))

    def appendlist(self, key: typing.Any, value: typing.Any) -> None:
        self._list.append((key, value))
        self._dict[key] = value

    def update(
        self,
        values: typing.Union[
            "MultiDict",
            typing.Mapping,
            typing.List[typing.Tuple[typing.Any, typing.Any]],
        ] = None,
        **kwargs: typing.Any,
    ) -> None:
        if values is None:
            items_ = []  # type: typing.List
        elif hasattr(values, "multi_items"):
            values = typing.cast(MultiDict, values)
            items_ = list(values.multi_items())
        elif hasattr(values, "items"):
            values = typing.cast(typing.Mapping, values)
            items_ = list(values.items())
        else:
            values = typing.cast(
                typing.List[typing.Tuple[typing.Any, typing.Any]], values
            )
            items_ = values
        keys = {k for k, _ in itertools.chain(items_, kwargs.items())}
        self._list = [
            *((k, v) for k, v in self._list if k not in keys),
            *items_,
            *list(kwargs.items()),
        ]

        self._dict.update(itertools.chain(items_, kwargs.items()))


class State(object):
    def __init__(self, state_dict: dict = {}):
        self._state = state_dict

    def __getattr__(self, __key):
        try:
            return self._state[__key]
        except KeyError:
            raise AttributeError(
                f"`{self.__class__.__name__}` has no attribute `{__key}`"
            )

    def __setattr__(self, __key, __value):
        if __key == "_state":
            super().__setattr__(__key, __value)
        else:
            self._state[__key] = __value

    def __iter__(self) -> Iterator:
        return enumerate(self._state)

    def __delattr__(self, __key):
        del self._state[__key]
