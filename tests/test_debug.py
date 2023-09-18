import pytest
import pytest_benchmark

pytest.skip("skipping", allow_module_level=True)


def fstring():
    a = "1"
    return f"{a}"


def format_string():
    a = "1"
    return "%s" % (a)


def test_string(benchmark):
    result = benchmark(fstring)
    assert result == "1"


def test_format_string(benchmark):
    result1 = benchmark(format_string)
    assert result1 == "1"
