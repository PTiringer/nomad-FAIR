import pytest

from nomad.metainfo.data_type import (
    JSON,
    Datetime,
    Enum,
    m_bool,
    m_float64,
    m_int64,
    m_str,
    to_json_schema_type,
)


@pytest.mark.parametrize(
    'input_type, expected',
    [
        (m_int64(), {'type': 'integer'}),
        (m_float64(), {'type': 'number'}),
        (m_bool(), {'type': 'boolean'}),
        (m_str(), {'type': 'string'}),
        (Enum('a', 'b'), {'type': 'string'}),
        (JSON(), {'type': 'object'}),
        (Datetime(), {'type': 'string', 'format': 'date-time'}),
    ],
)
def test_to_json_schema_type(input_type, expected):
    actual_schema = to_json_schema_type(input_type)
    assert actual_schema == expected


def test_to_json_schema_type_unsupported():
    class FakeType:
        def standard_type(self):
            return 'nope'

    with pytest.raises(NotImplementedError, match='Unsupported JSON Schema type'):
        to_json_schema_type(FakeType())
