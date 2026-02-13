import asyncio
from enum import Enum
from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_cache.decorator import cache
from pydantic import BaseModel

from nomad.actions.manager import (
    ActionModel,
    ActionModelSummary,
    ActionSchemaInfo,
    get_action_result,
    get_action_status,
    get_all_action_schemas,
    get_all_user_actions,
    get_user_action,
    start_action,
    stop_action,
    validate_action_arg,
)
from nomad.app.v1.models import User
from nomad.app.v1.routers.auth import get_current_user
from nomad.auth.scopes import Scope
from nomad.utils import strip

from ..models import HTTPExceptionModel
from ..utils import create_responses

router = APIRouter()


class APITag(str, Enum):
    DEFAULT = 'actions'


class ActionStart(BaseModel):
    data: dict


SCHEMA_CACHE_TTL: Final[int] = 1 * 24 * 60 * 60  # 1 day in seconds


@router.post(
    '/{action_id}/start',
    tags=[APITag.DEFAULT],
    summary='Start an action',
    description='Starts a new action with the given ID and input data.',
)
async def action_start(
    action_id: str,
    start_data: ActionStart,
    user: Annotated[
        User,
        Depends(get_current_user([Scope.ACTIONS_RUN], allow_anonymous=False)),
    ],
):
    """
    Starts a new action.

    Args:
        action_id: The ID of the action to start.
        start_data: The input data for the action.
        user: The authenticated user.

    Returns:
        The ID of the started action instance.
    """
    start_data.data['user_id'] = user.user_id
    try:
        input_data = validate_action_arg(action_id, start_data.data)
        action_instance_id = await asyncio.to_thread(
            lambda: start_action(action_id=action_id, data=input_data)
        )
        return {'action_instance_id': action_instance_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    '/{action_instance_id}/stop',
    tags=[APITag.DEFAULT],
    summary='Stop an action',
    description='Stops a running action instance.',
)
async def action_stop(
    action_instance_id: str,
    user: Annotated[
        User,
        Depends(
            get_current_user([Scope.ACTIONS_RUN], allow_anonymous=False),
        ),
    ],
):
    """
    Stops an action.

    Args:
        action_instance_id: The ID of the action instance to stop.
        user: The authenticated user.
    """
    try:
        await asyncio.to_thread(
            lambda: stop_action(
                action_instance_id=action_instance_id, user_id=user.user_id
            )
        )
        return {'status': 'stopped'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    '/{action_instance_id}/status',
    tags=[APITag.DEFAULT],
    summary='Get action status',
    description='Retrieves the current status of a specific action instance.',
)
async def action_status(
    action_instance_id: str,
    user: Annotated[
        User,
        Depends(
            get_current_user([Scope.ACTIONS_READ], allow_anonymous=False),
        ),
    ],
):
    """
    Gets the status of an action.

    Args:
        action_instance_id: The ID of the action instance.
        user: The authenticated user.

    Returns:
        The status of the action.
    """
    try:
        status = await asyncio.to_thread(
            lambda: get_action_status(
                action_instance_id=action_instance_id, user_id=user.user_id
            )
        )
        return {'status': status.name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    '/{action_instance_id}/result',
    tags=[APITag.DEFAULT],
    summary='Get action result',
    description='Retrieves the result of a specific action instance.',
)
async def action_result(
    action_instance_id: str,
    user: Annotated[
        User,
        Depends(
            get_current_user([Scope.ACTIONS_READ], allow_anonymous=False),
        ),
    ],
):
    """
    Gets the result of an action.

    Args:
        action_instance_id: The ID of the action instance.
        user: The authenticated user.

    Returns:
        The result of the action.
    """
    try:
        result = await asyncio.to_thread(
            lambda: get_action_result(
                action_instance_id=action_instance_id, user_id=user.user_id
            )
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    '/schemas',
    tags=[APITag.DEFAULT],
    response_model=list[ActionSchemaInfo],
    summary='Get action schemas',
    description='Retrieves the input schemas for all available actions.',
)
@cache(expire=SCHEMA_CACHE_TTL)
async def action_input_schemas(
    _user: Annotated[
        User,
        Depends(
            get_current_user([Scope.ACTIONS_READ], allow_anonymous=False),
        ),
    ],
):
    """
    Gets the input schemas for all available actions.

    Args:
        user: The authenticated user.

    Returns:
        A list of action input schemas.
    """
    try:
        result = await asyncio.to_thread(get_all_action_schemas)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


_not_authorized = (
    status.HTTP_401_UNAUTHORIZED,
    {
        'model': HTTPExceptionModel,
        'description': strip(
            """
        Unauthorized. Authorization is required, but no or bad authentication credentials provided."""
        ),
    },
)


@router.get(
    '/{action_instance_id}',
    tags=[APITag.DEFAULT],
    summary='Get a specific action of the authenticated user.',
    response_model=ActionModel,
    responses=create_responses(_not_authorized),
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
)
async def action(
    action_instance_id: str,
    user: Annotated[
        User,
        Depends(
            get_current_user([Scope.ACTIONS_READ], allow_anonymous=False),
        ),
    ],
):
    """
    Gets a specific action for the authenticated user.

    Args:
        action_instance_id: The ID of the action instance.
        user: The authenticated user.

    Returns:
        The action.
    """
    try:
        result = await asyncio.to_thread(
            lambda: get_user_action(
                action_instance_id=action_instance_id, user_id=user.user_id
            )
        )
        if result is None:
            raise HTTPException(status_code=404, detail='Action not found.')
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    '',
    tags=[APITag.DEFAULT],
    summary='List all actions of the authenticated user',
    description='Retrieves a list of all action instances initiated by the authenticated user.',
    response_model=list[ActionModelSummary],
    responses=create_responses(_not_authorized),
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
)
async def actions(
    user: Annotated[
        User,
        Depends(
            get_current_user([Scope.ACTIONS_READ], allow_anonymous=False),
        ),
    ],
):
    """
    Lists all actions for the authenticated user.

    Args:
        user: The authenticated user.

    Returns:
        A list of actions.
    """
    try:
        result = await asyncio.to_thread(
            lambda: get_all_user_actions(user_id=user.user_id)
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
