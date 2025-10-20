"""Shared utility functions for user groups."""

from __future__ import annotations

from collections.abc import Iterable

from nomad.app.v1.models.groups import UserGroupMember, UserGroupMemberRole


def _find_owners(members_info: Iterable[UserGroupMember]) -> list[UserGroupMember]:
    """Find all members with owner role."""
    return [m for m in members_info if m.role == UserGroupMemberRole.OWNER]


def validate_members_info(
    members_info: Iterable[UserGroupMember],
    expected_owner_id: str | None = None,
) -> None:
    """Validate members_info has exactly one owner and unique user_ids."""
    members_list = list(members_info)

    user_ids = [m.user_id for m in members_list]
    if len(user_ids) != len(set(user_ids)):
        raise ValueError('All user ids must be unique.')

    owners = _find_owners(members_list)
    if len(owners) != 1:
        raise ValueError('There must be exactly one owner.')

    if expected_owner_id and expected_owner_id != owners[0].user_id:
        raise ValueError(
            f'The owner of the group ({owners[0].user_id}) '
            f'must match the expected owner ({expected_owner_id}).'
        )


def convert_members_to_info(
    members: Iterable[str], owner_id: str
) -> list[UserGroupMember]:
    """Convert legacy members + owner format to members_info format."""
    no_owner_ids = set(members) - {owner_id}
    result = [UserGroupMember(user_id=owner_id, role=UserGroupMemberRole.OWNER)]
    result.extend(
        UserGroupMember(user_id=uid, role=UserGroupMemberRole.MEMBER)
        for uid in no_owner_ids
    )
    return result


def get_owner_and_members(
    members_info: Iterable[UserGroupMember],
) -> tuple[str, list[str]]:
    """Extract owner_id and members list from members_info."""
    members_list = list(members_info)
    owners = _find_owners(members_list)
    owner_id = owners[0].user_id
    all_members = [m.user_id for m in members_list]
    return owner_id, all_members


def merge_info_with_members(
    info: Iterable[UserGroupMember], members: Iterable[str], owner_id: str
) -> list[UserGroupMember]:
    """Return a new members_info list with membership updated by (deprecated) members list.

    The given owner is ensured.
    If a member is in both lists, their attributes are kept.
    """
    owner = next(m for m in info if m.user_id == owner_id)
    new_info = [
        owner or UserGroupMember(user_id=owner_id, role=UserGroupMemberRole.OWNER)
    ]

    info_ids = {m.user_id for m in info} - {owner_id}
    edit_ids = set(members) - {owner_id}
    keep_ids = info_ids & edit_ids
    new_info.extend(m for m in info if m.user_id in keep_ids)

    add_ids = edit_ids - info_ids
    new_info.extend(UserGroupMember(user_id=m) for m in add_ids)

    print('Merged members_info:', new_info)
    return new_info


def get_user_role(
    members_info: Iterable[UserGroupMember], user_id: str
) -> UserGroupMember | None:
    """Find a user's membership record in a group."""
    for member in members_info:
        if member.user_id == user_id:
            return member
    return None
