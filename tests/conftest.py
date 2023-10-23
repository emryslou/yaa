import functools, pytest

from yaa import TestClient


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"use_uvloop": False}), id="asyncio"),
        pytest.param(("trio", {"strict_exception_groups": False}), id="trio"),
    ],
    autouse=True,
)
def anyio_backend(request):
    return request.param


@pytest.fixture
def no_trio_support(anyio_backend_name):
    if anyio_backend_name == "trio":
        pytest.skip("Trio not supported (yet!)")


@pytest.fixture
def client_factory(anyio_backend_name, anyio_backend_options):
    return functools.partial(
        TestClient, backend=anyio_backend_name, backend_options=anyio_backend_options
    )
