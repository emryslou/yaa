import os

import pytest

from yaa.config import Config


def test_config(tmpdir):
    path = os.path.join(tmpdir, ".env")

    with open(path, "w") as file:
        file.write("# Do not commit to source \n")
        file.write("AA = CC\n")
        file.write("BB = 12\n")
        file.write("CC = true\n")
        file.write("DD = false\n")
        file.write("EE01 = 1\n")
        file.write("FF01 = 0\n")
        file.write("PASSWD = abcd123")

    config = Config(path, environ={"DEBUG": "true"})

    debug = config.get("DEBUG", cast=bool)
    assert debug is True

    aa = config.get("AA")
    assert aa == "CC"

    bb = config.get("BB")
    assert bb == "12"
    bb_int = config.get("BB", cast=int)
    assert isinstance(bb_int, int)
    assert bb_int == 12

    cc = config.get("CC")
    assert cc == "true"
    cc_bool = config.get("CC", cast=bool)
    assert isinstance(cc_bool, bool)
    assert cc_bool is True

    with pytest.raises(KeyError):
        config.get("FF")

    with pytest.raises(ValueError):
        config.get("AA", cast=bool)

    with pytest.raises(ValueError):
        config.get("AA", cast=int)

    ff = config.get("FF", default="FF")
    assert ff == "FF"

    secrect = config.get("PASSWD")
    assert secrect == "abcd123"

    from yaa.datastructures import Secret

    secrect = config.get("PASSWD", cast=Secret)
    assert repr(secrect) == "Secret('********')"
    assert str(secrect) == "abcd123"

    assert config.get("EE01") == "1"
    assert config.get("EE01", cast=bool) == True
    assert config.get("FF01") == "0"
    assert config.get("FF01", cast=bool) == False


def test_no_env_file(tmpdir):
    config = Config(tmpdir + "/no.env")
    assert config.file_values == {}


def test_environ(client_factory):
    from yaa.config import Environ, EnvironError

    environ = Environ()
    environ["DEBUG"] = "True"
    environ["CANDEL"] = "aaa"
    del environ["CANDEL"]
    assert "CANDEL" not in environ

    assert environ["DEBUG"] == "True"
    with pytest.raises(EnvironError):
        del environ["DEBUG"]

    with pytest.raises(EnvironError):
        environ["DEBUG"] = "False"

    environ = Environ()
    assert list(iter(environ)) == list(iter(os.environ))
    assert len(environ) == len(os.environ)


def test_config_types() -> None:
    from typing_extensions import assert_type
    from typing import Optional, Any

    """
    We use `assert_type` to test the types returned by Config via mypy.
    """
    config = Config(
        environ={"STR": "some_str_value", "STR_CAST": "some_str_value", "BOOL": "true"}
    )
    assert_type(config("STR"), str)
    assert_type(config("STR_DEFAULT", default=""), str)
    assert_type(config("STR_CAST", cast=str), str)
    assert_type(config("STR_NONE", default=None), Optional[str])
    assert_type(config("STR_CAST_NONE", cast=str, default=None), Optional[str])
    assert_type(config("STR_CAST_STR", cast=str, default=""), str)
    assert_type(config("BOOL", cast=bool), bool)
    assert_type(config("BOOL_DEFAULT", cast=bool, default=False), bool)
    assert_type(config("BOOL_NONE", cast=bool, default=None), Optional[bool])

    def cast_to_int(v: Any) -> int:
        return int(v)

    # our type annotations allow these `cast` and `default` configurations, but
    # the code will error at runtime.
    with pytest.raises(ValueError):
        config("INT_CAST_DEFAULT_STR", cast=cast_to_int, default="true")
    with pytest.raises(ValueError):
        config("INT_DEFAULT_STR", cast=int, default="true")


def test_config_with_env_prefix(tmpdir, monkeypatch):
    config = Config(
        environ={"APP_DEBUG": "value", "ENVIRONMENT": "dev"}, env_prefix="APP_"
    )
    assert config.get("DEBUG") == "value"
    with pytest.raises(KeyError):
        config.get("ENVIRONMENT")
