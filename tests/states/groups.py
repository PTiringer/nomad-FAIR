from collections.abc import Iterable

from nomad.app.v1.models.groups import UserGroupMember
from nomad.auth import user_manage
from nomad.mongo.groups import create_mongo_user_group_for_test, get_mongo_user_group
from tests.utils import list_without


def _create(group_id: str, group_name: str, owner: str, members: Iterable[str]):
    no_owner_ids = list_without(members, owner)
    members = [owner] + no_owner_ids
    members_info = [UserGroupMember(user_id=owner, role='owner')]
    members_info.extend(
        UserGroupMember(user_id=uid, role='member') for uid in no_owner_ids
    )

    return create_mongo_user_group_for_test(
        group_id=group_id,
        group_name=group_name,
        owner=owner,
        members=members,
        members_info=members_info,
    )


def delete_group(group_id):
    get_mongo_user_group(group_id).delete()


def init_gui_test_groups():
    user0 = user_manage.user_management.get_user(username='admin').user_id
    user1 = user_manage.user_management.get_user(username='test').user_id
    user2 = user_manage.user_management.get_user(username='scooper').user_id
    user3 = user_manage.user_management.get_user(username='ttester').user_id

    groups = {
        'group0': (
            'group0',
            'Group Admin',
            user0,
        ),
        'group1': ('group1', 'Group Test', user1),
        'group2': ('group2', 'Group Cooper', user2),
        'group3': ('group3', 'Group Tester', user3),
        'group23': ('group23', 'Group 23', user2, [user3]),
    }
    groups = {k: _create(*args) for k, args in groups.items()}

    return groups
