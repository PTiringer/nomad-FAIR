import pytest
from nomad.app.v1.utils import get_query_keys


@pytest.mark.parametrize(
    'source, exclude_keys, expected_keys',
    [
        pytest.param({'a': 1, 'b': 2}, None, {'a', 'b'}, id='simple_dict'),
        pytest.param([{'a': 1}, {'b': 2}], None, {'a', 'b'}, id='list_of_dicts'),
        pytest.param({'a': {'b': 1, 'c': 2}}, None, {'a.b', 'a.c'}, id='nested_dict'),
        pytest.param(
            {'a': [{'b': 1}, {'c': 2}]}, None, {'a.b', 'a.c'}, id='dict_with_list'
        ),
        pytest.param({'a': 1, 'b': 2}, ['a'], {'b'}, id='with_exclude'),
        pytest.param(
            {'a': {'b': 1, 'c': 2}}, ['a'], {'b', 'c'}, id='nested_with_exclude'
        ),
        pytest.param({}, None, set(), id='empty_dict'),
        pytest.param([], None, set(), id='empty_list'),
        pytest.param({'a': []}, None, {'a'}, id='dict_with_empty_list'),
        pytest.param({'a': {}}, None, {'a'}, id='dict_with_empty_dict'),
    ],
)
def test_get_query_keys(source, exclude_keys, expected_keys):
    assert get_query_keys(source, exclude_keys) == expected_keys
