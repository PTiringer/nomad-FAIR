from typing import List, Optional, Set

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    root_validator,
    validator,
)
from pydantic_core import PydanticCustomError

from .pagination import Direction, Pagination, PaginationResponse

group_name_description = 'Name of the group.'
group_members_description = 'User ids of the group members.'


class UserGroupEdit(BaseModel):
    group_name: str | None = Field(
        default=None,
        description=group_name_description,
        min_length=3,
        max_length=32,
        pattern=r'^[a-zA-Z0-9][a-zA-Z0-9 ._\-]+[a-zA-Z0-9]$',
    )
    members: set[str] | None = Field(
        default=None, description=group_members_description
    )


class UserGroup(BaseModel):
    group_id: str = Field(description='Unique id of the group.')
    group_name: str = Field(
        default='Default Group Name', description=group_name_description
    )
    owner: str = Field(description='User id of the group owner.')
    members: list[str] = Field(
        default_factory=list, description=group_members_description
    )

    model_config = ConfigDict(from_attributes=True)


class UserGroupResponse(BaseModel):
    pagination: PaginationResponse | None = Field(None)
    data: list[UserGroup]


class UserGroupQuery(BaseModel):
    group_id: list[str] | None = Field(
        None, description='Search groups by their full id.'
    )
    user_id: str | None = Field(
        None, description='Search groups by their owner or members ids.'
    )
    search_terms: str | None = Field(
        None, description='Search groups by parts of their name.'
    )


class UserGroupPagination(Pagination):
    @field_validator('order_by')
    @classmethod
    def validate_order_by(cls, order_by):  # pylint: disable=no-self-argument
        valid_fields = (None, 'group_id', 'group_name', 'owner')
        if order_by not in valid_fields:
            raise PydanticCustomError(
                'invalid_order_by', f'order_by must be one of {valid_fields}'
            )
        return order_by

    def order_result(self, result):
        if self.order_by is None:
            return result

        prefix: str = '-' if self.order == Direction.desc else '+'
        order_list: list = [f'{prefix}{self.order_by}', 'group_id']

        return result.order_by(*order_list)
