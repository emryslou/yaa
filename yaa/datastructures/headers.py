import typing

from yaa.types import Scope, T


class Headers(typing.Mapping[str, str]):
    """headers"""

    def __init__(
        self,
        headers: typing.Optional[typing.Mapping[str, str]] = None,
        raw: typing.Optional[typing.List[typing.Tuple[bytes, bytes]]] = None,
        scope: typing.Optional[Scope] = None,
    ) -> None:
        self._list = []
        if headers is not None:
            assert raw is None, "Cannot set both `headers` and `raw`"
            assert scope is None, "Cannot set both `headers` and `scope`"
            self._list = [
                (key.lower().encode("latin-1"), value.encode("latin-1"))
                for key, value in headers.items()
            ]
        elif raw is not None:
            assert scope is None, "Cannot set both `raw` and `scope`"
            self._list = raw
        elif scope is not None:
            self._list = scope["headers"]

    @property
    def raw(self) -> typing.List[typing.Tuple[bytes, bytes]]:
        return list(self._list)

    def keys(self) -> typing.List[str]:  # type: ignore[override]
        return [key.decode("latin-1") for key, _ in self._list]

    def values(self) -> typing.List[str]:  # type: ignore[override]
        return [value.decode("latin-1") for _, value in self._list]

    def items(self) -> typing.List[typing.Tuple[str, str]]:  # type: ignore[override]
        return [(k.decode("latin-1"), v.decode("latin-1")) for k, v in self._list]

    def get(self, key: str, default: typing.Optional[str] = None) -> typing.Optional[str]:  # type: ignore[override]
        try:
            return self[key]
        except KeyError:
            return default

    def getlist(self, key: str) -> typing.List[str]:
        h_k = key.lower().encode("latin-1")
        return [iv.decode("latin-1") for ik, iv in self._list if ik == h_k]

    def mutablecopy(self) -> "MutableHeaders":
        return MutableHeaders(raw=self._list[:])

    def __getitem__(self, key: str) -> str:
        h_k = key.lower().encode("latin-1")
        for ik, iv in self._list:
            if h_k == ik:
                return iv.decode("latin-1")

        raise KeyError(key)

    def __contains__(self, key: str) -> bool:  # type: ignore
        return key.lower() in self.keys()

    def __iter__(self) -> typing.Iterator:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._list)

    def __eq__(self, other: T) -> bool:
        if not isinstance(other, Headers):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self) -> str:
        as_dict = dict(self.items())
        if len(as_dict) == len(self):
            return f"{self.__class__.__name__}({repr(self.items())})"
        return f"{self.__class__.__name__}(raw={repr(self.raw)})"


class MutableHeaders(Headers):
    def __setitem__(self, key: str, value: str) -> None:
        set_key = key.lower().encode("latin-1")
        set_value = value.encode("latin-1")

        pop_indexes = []
        for idx, (ik, _) in enumerate(self._list):
            if ik == set_key:
                pop_indexes.append(idx)

        """
        retain insertion order .
        """
        for idx in reversed(pop_indexes[1:]):
            del self._list[idx]

        if pop_indexes:
            self._list[pop_indexes[0]] = (set_key, set_value)
        else:
            self._list.append((set_key, set_value))

    def __delitem__(self, key: str) -> None:
        del_key = key.lower().encode("latin-1")
        pop_indexes = []
        for idx, (ik, _) in enumerate(self._list):
            if ik == del_key:
                pop_indexes.append(idx)

        for idx in reversed(pop_indexes):
            del self._list[idx]

    @property
    def raw(self) -> typing.List[typing.Tuple[bytes, bytes]]:
        return self._list

    def __ior__(self, other: typing.Mapping) -> "MutableHeaders":
        """
        x = MutableHeaders(...), y = MutableHeaders(...)
        x |= y
        c = x | y
        """
        if not isinstance(other, typing.Mapping):
            raise TypeError(f"Expected a mapping but got {other.__class__.__name__}")
        new = self.mutablecopy()
        new.update(other)
        return new

    def __or__(self, other: typing.Mapping) -> "MutableHeaders":
        """
        x = MutableHeaders(...), y = MutableHeaders(...)
        x |= y
        c = x | y
        """
        if not isinstance(other, typing.Mapping):
            raise TypeError(f"Expected a mapping but got {other.__class__.__name__}")
        new = self.mutablecopy()
        new.update(other)
        return new

    def setdefault(self, key: str, value: str) -> str:
        set_key = key.lower().encode("latin-1")
        set_value = value.encode("latin-1")

        for _, (itm_key, itm_val) in enumerate(self._list):
            if itm_key == set_key:
                return itm_val.decode("latin-1")

        self._list.append((set_key, set_value))
        return value

    def update(self, other: typing.Mapping) -> None:
        for key, val in other.items():
            self[key] = val

    def append(self, key: str, value: str) -> None:
        app_key = key.lower().encode("latin-1")
        app_val = value.encode("latin-1")
        self._list.append((app_key, app_val))

    def add_vary_header(self, vary: str) -> None:
        existing = self.get("vary")
        if existing is not None:
            vary = ", ".join([existing, vary])

        self["vary"] = vary
