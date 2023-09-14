import os
import typing
from collections.abc import MutableMapping


class Undefined(object):
    pass


class EnvironError(Exception):
    pass


class Config(object):
    def __init__(
        self, env_file: str = None, environ: typing.Mapping[str, str] = os.environ
    ) -> None:
        self.environ = environ
        self.file_values = {}
        if env_file is not None:
            self.file_values = self._load_from(env_file)

    def _load_from(self, load_file: str, file_type: str = "env") -> dict:
        if not os.path.exists(load_file):
            return {}

        load_fn = "_load_from_%s" % file_type
        if not hasattr(self, load_fn):
            return {}  # pragma: nocover

        return getattr(self, load_fn)(load_file)

    def _load_from_env(self, load_file: str) -> dict:
        file_values = {}
        with open(load_file) as ifile:
            for line in ifile.readlines():
                if line.startswith("#"):
                    continue
                if "=" in line and not line.startswith("="):
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    file_values[key] = value
        return file_values

    def get(
        self, key: str, cast: type = None, default: typing.Any = Undefined
    ) -> typing.Any:
        if key in self.environ:
            return self._cast(
                key=key, value=self.environ[key], cast=cast, default=default
            )

        if key in self.file_values:
            return self._cast(
                key=key, value=self.file_values[key], cast=cast, default=default
            )

        if default is not Undefined:
            return default

        raise KeyError("'Config '%s' is missing, and has no default'" % key)

    def _cast(
        self,
        key: str,
        value: typing.Any,
        cast: type = None,
        default: typing.Any = Undefined,
    ) -> typing.Any:
        if cast is None:
            return value
        elif cast is bool and isinstance(value, str):
            _bool_map = {
                "true": True,
                "false": False,
            }
            if value not in _bool_map:
                raise ValueError(
                    'Config "%s" has value "%s". But not a valid bool' % (key, value)
                )
            return _bool_map[value]

        try:
            return cast(value)
        except (TypeError, ValueError):
            raise ValueError(
                'Config "%s" has value "%s". But not a valid %s'
                % (key, value, cast.__name__)
            )


class Environ(MutableMapping):
    def __init__(self, environ: typing.MutableMapping = os.environ) -> None:
        self._environ = environ
        self._has_been_read = set()

    def __getitem__(self, key: typing.Any) -> typing.Any:
        self._has_been_read.add(key)
        return self._environ.__getitem__(key)

    def __setitem__(self, key: typing.Any, value: typing.Any) -> None:
        if key in self._has_been_read:
            raise EnvironError(
                f"Attempting to set environ [`{key}`]"
                ", but the value has already be read"
            )
        self._environ.__setitem__(key, value)

    def __delitem__(self, key: typing.Any) -> None:
        if key in self._has_been_read:
            raise EnvironError(
                f"Attempting to del environ [`{key}`]"
                ", but the value has already be read"
            )
        self._environ.__delitem__(key)

    def __iter__(self) -> typing.Iterator:
        return iter(self._environ)

    def __len__(self) -> int:
        return len(self._environ)


environ = Environ()
