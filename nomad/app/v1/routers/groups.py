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

from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Request, status

from nomad.app.v1.models.groups import (
    UserGroup,
    UserGroupEdit,
    UserGroupPagination,
    UserGroupQuery,
    UserGroupResponse,
)
from nomad.app.v1.models.pagination import PaginationResponse
from nomad.app.v1.utils import parameter_dependency_from_model
from nomad.datamodel import User as UserDataModel
from nomad.groups import MongoUserGroup, create_mongo_user_group, get_mongo_user_group
from nomad.utils import strip

from ..models import User
from .auth import create_user_dependency

router = APIRouter()


class APITag(str, Enum):
    DEFAULT = 'groups'


user_group_query_parameters = parameter_dependency_from_model(
    'user_group_query_parameters',
    UserGroupQuery,  # type: ignore
)

user_group_pagination_parameters = parameter_dependency_from_model(
    'user_group_pagination_parameters',
    UserGroupPagination,  # type: ignore
)


def get_user_group_or_404(group_id: str) -> MongoUserGroup:
    user_group = get_mongo_user_group(group_id)
    if user_group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User group '{group_id}' was not found.",
        )

    return user_group


def check_user_ids(user_ids):
    """Raise 404 NOT FOUND if user id is not in database."""
    for user_id in user_ids:
        try:
            UserDataModel.get(user_id=user_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' was not found.",
            ) from exc


def check_user_may_edit_user_group(user: User, user_group: MongoUserGroup):
    if user.is_admin or user.user_id == user_group.owner:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=strip(
            f"Not authorized to edit user group '{user_group.group_id}'."
            ' Only group owners and admins are allowed to edit a group.'
        ),
    )


@router.get(
    '',
    tags=[APITag.DEFAULT],
    summary='List user groups. Use at most one filter.',
    response_model=UserGroupResponse,
)
async def get_user_groups(
    request: Request,
    query: UserGroupQuery = Depends(user_group_query_parameters),
    pagination: UserGroupPagination = Depends(user_group_pagination_parameters),
):
    """Get data about user groups."""
    db_groups = MongoUserGroup.get_by_query(query)
    db_groups = pagination.order_result(db_groups)

    total = db_groups.count()
    pagination_response = PaginationResponse(total=total, **pagination.dict())
    pagination_response.populate_simple_index_and_urls(request)

    start = pagination.get_simple_index()
    end = start + pagination.page_size
    data = [UserGroup.from_orm(group) for group in db_groups[start:end]]
    return {'pagination': pagination_response, 'data': data}


@router.get(
    '/{group_id}',
    tags=[APITag.DEFAULT],
    summary='Get data about user group.',
    response_model=UserGroup,
)
async def get_user_group(group_id: str):
    """Get data about user group."""
    user_group = get_user_group_or_404(group_id)

    return user_group


@router.post(
    '',
    tags=[APITag.DEFAULT],
    status_code=status.HTTP_201_CREATED,
    summary='Create user group.',
    response_model=UserGroup,
)
async def create_user_group(
    user_group_edit: UserGroupEdit,
    user: User = Depends(create_user_dependency(required=True)),
):
    """Create user group."""
    user_group_dict = user_group_edit.dict(exclude_none=True)
    members = user_group_dict.get('members')
    if members is not None:
        check_user_ids(members)
    user_group_dict['owner'] = user.user_id

    user_group = create_mongo_user_group(**user_group_dict)
    return user_group


@router.post(
    '/{group_id}/edit',
    tags=[APITag.DEFAULT],
    summary='Update user group.',
    response_model=UserGroup,
)
async def update_user_group(
    group_id: str,
    user_group_edit: UserGroupEdit,
    user: User = Depends(create_user_dependency(required=True)),
):
    """Update user group."""
    user_group = get_user_group_or_404(group_id)
    check_user_may_edit_user_group(user, user_group)

    user_group_dict = user_group_edit.dict(exclude_none=True)
    members = user_group_dict.get('members')
    if members is not None:
        check_user_ids(members)

    user_group.clean_update_reload(**user_group_dict)
    return user_group


@router.delete(
    '/{group_id}',
    tags=[APITag.DEFAULT],
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Delete user group.',
)
async def delete_user_group(
    group_id: str, user: User = Depends(create_user_dependency(required=True))
):
    """Delete user group."""
    user_group = get_user_group_or_404(group_id)
    check_user_may_edit_user_group(user, user_group)

    user_group.delete()
