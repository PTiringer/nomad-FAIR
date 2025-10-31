"""
Group fixtures:
- groupO: group owned by userO without members
- groupOMN…: group owned by userO with members userM, userN, …
- special (unfinished) groups, often only partly defined
"""

import pytest

from nomad.mongo.groups import create_mongo_user_group
from tests.utils import fake_group_uuid, fake_user_uuid, generate_convert_label


@pytest.fixture(scope='session')
def group_molds():
    """Return a dict: group label -> group data (dict)."""

    def default_group(owner, members, group_str=None):
        if group_str is None:
            group_str = str(owner) + ''.join(str(m) for m in members if m != owner)

        return dict(
            group_id=fake_group_uuid(group_str),
            group_name=f'Group {group_str}',
            owner=fake_user_uuid(owner),
            members=[fake_user_uuid(member) for member in members],
        )

    def custom_group(group_name, members, owner=None):
        mold = dict(
            group_name=group_name,
            members=[fake_user_uuid(member) for member in members],
        )
        if owner is not None:
            mold['owner'] = fake_user_uuid(owner)
        return mold

    default_groups = {
        'group0': default_group(0, [0]),
        'group1': default_group(1, [1]),
        'group2': default_group(2, [2]),
        'group3': default_group(3, [3]),
        'group6': default_group(6, [6]),
        'group8': default_group(8, [8]),
        'group9': default_group(9, [9]),
        'group14': default_group(1, [1, 4]),
        'group15': default_group(1, [1, 5]),
        'group18': default_group(1, [1, 8]),
        'group19': default_group(1, [1, 9]),
        'group123': default_group(1, [1, 2, 3]),
        'uniq': default_group(0, [0], 'Uniq'),
        'twin1': default_group(0, [0], 'Twin One'),
        'twin2': default_group(0, [0], 'Twin Two'),
        'numerals': default_group(0, [0], 'One Two Three'),
    }

    custom_groups = {
        'new_group': custom_group('New Group X23', [2, 3]),
        'new_group_ref1': custom_group('New Group X23', [1, 2, 3]),
        'new_group_ref2': custom_group('New Group X23', [2, 3]),
        'double_member': custom_group('Double Member', [2, 3, 2]),
        'double_member_ref': custom_group('Double Member', [1, 2, 3]),
        'short_name': custom_group('G', [1], owner=1),
        'long_name': custom_group('G' * 65, [1], owner=1),
        'whitespace_name': custom_group(' \t ', [1], owner=1),
        'special_chars_name': custom_group(
            '!@#$%^&*()_+-=[]}\r\t\n{:; "\'|\\<,>.?/…😀', [1], owner=1
        ),
        'owner_not_member': custom_group('Owner Not Member', [2, 3], owner=1),
        'owner_not_member_ref': custom_group('Owner Not Member', [1, 2, 3], owner=1),
    }

    return {**default_groups, **custom_groups}


@pytest.fixture(scope='session')
def group_label_id_mapping(group_molds):
    """Return a dict: group label -> group id."""
    return {label: value.get('group_id') for label, value in group_molds.items()}


@pytest.fixture(scope='session')
def convert_group_labels_to_ids(group_label_id_mapping):
    """Returned function converts group labels to ids, also in lists and dicts."""
    return generate_convert_label(group_label_id_mapping)


@pytest.fixture(scope='session')
def convert_agent_labels_to_ids(user_label_id_mapping, group_label_id_mapping):
    """Returned function converts agent labels to ids, also in lists and dicts."""
    is_disjoint = set(user_label_id_mapping).isdisjoint(group_label_id_mapping)
    assert is_disjoint, 'Duplicate labels in users and groups.'
    mapping = {**user_label_id_mapping, **group_label_id_mapping}
    return generate_convert_label(mapping)


@pytest.fixture(scope='session')
def create_user_groups(group_molds):
    """Returned function creates and returns predefined user groups for testing."""

    def create():
        groups_with_id = {k: v for k, v in group_molds.items() if 'group_id' in v}
        user_groups = {
            k: create_mongo_user_group(**v) for k, v in groups_with_id.items()
        }

        return user_groups

    return create


@pytest.fixture(scope='module')
def groups_module(mongo_module, create_user_groups):
    """Create and return predefined user groups for testing (module scope)."""
    return create_user_groups()


@pytest.fixture
def groups_function(mongo_function, create_user_groups):
    """Create and return predefined user groups for testing (function scope)."""
    return create_user_groups()


@pytest.fixture
def group_owner_not_member(mongo_function, group_molds):
    """Create and return a group where owner is not a member (old behavior)."""
    mold = group_molds['owner_not_member']
    group = create_mongo_user_group(**mold, _clean=False)
    return group
