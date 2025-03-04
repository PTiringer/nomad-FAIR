#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD. See https://nomad-lab.eu for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from __future__ import annotations

from typing import Optional, Union
from collections.abc import Iterable

from mongoengine import Document, ListField, Q, QuerySet, StringField

from nomad.app.v1.models.groups import UserGroupQuery
from nomad.utils import create_uuid


class MongoUserGroup(Document):
    """
    A group of users. One user is the owner, all others are members.
    """

    id_field = 'group_id'

    group_id = StringField(primary_key=True)
    group_name = StringField()
    owner = StringField(required=True)
    members = ListField(StringField())

    meta = {
        'collection': 'user_group',
        'indexes': ['group_name', 'owner', 'members'],
    }

    @classmethod
    def q_by_ids(cls, group_ids: str | Iterable[str]) -> Q:
        """
        Returns UserGroup Q for group_ids.
        """
        if isinstance(group_ids, str):
            return Q(group_id=group_ids)
        else:
            return Q(group_id__in=group_ids)

    @classmethod
    def q_by_user_id(cls, user_id: str | None) -> Q:
        """
        Returns UserGroup Q where user_id is owner or member, or None.

        Does not imply special group 'all' because it has no UserGroup object.
        """
        return Q(owner=user_id) | Q(members=user_id)

    @classmethod
    def q_by_search_terms(cls, search_terms: str) -> Q:
        """
        Returns UserGroup Q where group_name includes search_terms (no case).

        Each space-separated term must be included in group_name.
        """
        q = Q()
        for term in search_terms.split():
            q &= Q(group_name__icontains=term)

        return q

    @classmethod
    def get_by_query(cls, query: UserGroupQuery) -> QuerySet:
        """
        Returns UserGroup objects according to query, sub queries are connect by AND.
        """
        q = Q()
        if query.group_id is not None:
            q &= cls.q_by_ids(query.group_id)
        if query.user_id is not None:
            q &= cls.q_by_user_id(query.user_id)
        if query.search_terms is not None:
            q &= cls.q_by_search_terms(query.search_terms)

        return cls.objects(q)

    @classmethod
    def get_ids_by_user_id(cls, user_id: str | None, include_all=True) -> list[str]:
        """
        Returns ids of all user groups where user_id is owner or member.

        When include_all is true, special group 'all' is included,
        even if user_id is missing or not a user.
        """
        group_ids = ['all'] if include_all else []
        if user_id is not None:
            q = cls.q_by_user_id(user_id)
            groups = cls.objects(q)
            group_ids.extend(group.group_id for group in groups)
        return group_ids


def create_user_group(
    *,
    group_id: str | None = None,
    group_name: str | None = None,
    owner: str | None = None,
    members: Iterable[str] | None = None,
) -> MongoUserGroup:
    user_group = MongoUserGroup(
        group_id=group_id, group_name=group_name, owner=owner, members=members
    )
    if user_group.group_id is None:
        user_group.group_id = create_uuid()
    if user_group.group_name is None:
        user_group.group_name = user_group.group_id
    user_group.save()

    return user_group


def get_user_ids_by_group_ids(group_ids: list[str]) -> set[str]:
    user_ids = set()

    q = MongoUserGroup.q_by_ids(group_ids)
    groups = MongoUserGroup.objects(q)
    for group in groups:
        user_ids.add(group.owner)
        user_ids.update(group.members)

    return user_ids


def get_user_group(group_id: str) -> MongoUserGroup | None:
    q = MongoUserGroup.q_by_ids(group_id)
    return MongoUserGroup.objects(q).first()


def user_group_exists(group_id: str, *, include_all=True) -> bool:
    if include_all and group_id == 'all':
        return True
    return get_user_group(group_id) is not None


def get_group_ids(user_id: str, include_all=True) -> list[str]:
    return MongoUserGroup.get_ids_by_user_id(user_id, include_all=include_all)
