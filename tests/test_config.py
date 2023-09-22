import os

import pytest

from yast.config import Config


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

    from yast.datastructures import Secret

    secrect = config.get("PASSWD", cast=Secret)
    assert repr(secrect) == "Secret('********')"
    assert str(secrect) == "abcd123"

    assert config.get('EE01') == '1'
    assert config.get('EE01', cast=bool) == True
    assert config.get('FF01') == '0'
    assert config.get('FF01', cast=bool) == False


def test_no_env_file(tmpdir):
    config = Config(tmpdir + "/no.env")
    assert config.file_values == {}


def test_environ():
    from yast.config import Environ, EnvironError

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
