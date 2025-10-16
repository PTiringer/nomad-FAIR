import pytest


@pytest.mark.parametrize(
    'entry, method_identified', [('hash_exciting', True), ('hash_vasp', False)]
)
def test_method_id(entry, method_identified, request):
    """Test that method_id can be detected or is left undetected from certain
    calculations.
    """
    entry = request.getfixturevalue(entry)
    assert (entry.results.method.method_id is not None) == method_identified
    assert (entry.results.method.equation_of_state_id is not None) == method_identified
    assert (
        entry.results.method.parameter_variation_id is not None
    ) == method_identified
