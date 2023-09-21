import pytest
import pytest_benchmark

# pytest.skip("skipping", allow_module_level=True)


def test_open_file(tmpdir):
    import os

    path = os.path.join(tmpdir, "text.111")
    with open(path, "w") as f:
        f.write("<file content>")

    assert os.path.isfile(path)
