import math
import typing


class Convertor(object):
    regex = ""

    def convert(self, value: str) -> typing.Any:
        raise NotImplementedError()  # pragma: no cover

    def to_string(self, value: typing.Any) -> str:
        raise NotImplementedError()  # pragma: no cover


class StringConvertor(Convertor):
    regex = "[^/]+"

    def convert(self, value: str) -> typing.Any:
        return value

    def to_string(self, value: typing.Any) -> str:
        value = str(value)
        assert "/" not in value, 'May not contain path "/"'
        return value


class PathConvertor(Convertor):
    regex = ".*"

    def convert(self, value: str) -> typing.Any:
        return value

    def to_string(self, value: typing.Any) -> str:
        return str(value)


class IntegerConvertor(Convertor):
    regex = "[+]?[0-9]+"

    def convert(self, value: str) -> int:
        return int(value)

    def to_string(self, value: typing.Any) -> str:
        value = int(value)
        assert value >= 0, "Negative integers are not supported"
        return str(value)


class FloatConvertor(Convertor):
    regex = "[0-9]+(.[0-9]+)?"

    def convert(self, value: str) -> typing.Any:
        return float(value)

    def to_string(self, value: typing.Any) -> str:
        value = float(value)
        assert value >= 0.0, "Negative floats are not supported"
        assert not math.isnan(value), "NaN values are not supported"
        assert not math.isinf(value), "Infinite values are not supported"

        # bug: float('12.345') => 12.34559999999999924114
        return ("%0.20f" % value).rstrip("0").rstrip(".")


CONVERTOR_TYPES = {
    "str": StringConvertor(),
    "path": PathConvertor(),
    "int": IntegerConvertor(),
    "float": FloatConvertor(),
}
