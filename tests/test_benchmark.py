import pytest

pytest.skip("benchmark skip", allow_module_level=True)


def fn_s(loop_times=1):
    return "%s %s %d" % ("aa", "bb", 45)


def fn_replace(loop_times=1):
    return "{} {} {}".format("aa", "bb", 45)


def test_s(benchmark):
    s = benchmark(fn_s)
    assert s == "aa bb 45"


def test_replace(benchmark):
    s = benchmark(fn_replace)
    assert s == "aa bb 45"
