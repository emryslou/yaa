import datetime
import pytest

from yaa import convertors
from yaa.convertors import Convertor, register_url_convertor
from yaa.routing import Route, Router
from yaa.responses import JSONResponse


@pytest.fixture(scope="module", autouse=True)
def refresh_convertor_types():
    convert_types = convertors.CONVERTOR_TYPES.copy()
    yield
    convertors.CONVERTOR_TYPES = convert_types


class DateTimeConvertor(Convertor):
    regex = "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(.[0-9]+)?"
    name = 'datetime'

    def convert(self, value: str) -> datetime.datetime:
        return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
    
    def to_string(self, value: datetime.datetime) -> str:
        return value.strftime('%Y-%m-%dT%H:%M:%S')


@pytest.fixture(scope='function')
def app() -> Router:
    register_url_convertor('datetime', DateTimeConvertor())
    def datetime_convertor(req):
        param = req.path_params['param']
        assert isinstance(param, datetime.datetime)
        return JSONResponse({'datetime': param.strftime('%Y-%m-%dT%H:%M:%S')})
    
    return Router(
        routes=[
            Route(
                '/datetime/{param:datetime}',
                endpoint=datetime_convertor,
                name='datetime-convertor',
            )
        ]
    )


def test_my_convert(client_factory, app):
    client = client_factory(app)
    res = client.get('/datetime/2023-01-02T01:02:03')
    assert res.json() == {"datetime": "2023-01-02T01:02:03"}

    assert (
        app.url_path_for('datetime-convertor', param=datetime.datetime(2024, 11, 11, 11, 11, 11))
        == '/datetime/2024-11-11T11:11:11'
    )
