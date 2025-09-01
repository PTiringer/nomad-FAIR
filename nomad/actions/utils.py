import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from temporalio.client import WorkflowExecutionStatus

from nomad import infrastructure
from nomad.actions.action import get_actions
from nomad.actions.client import get_client
from nomad.config import config
from nomad.files import StagingUploadFiles
from nomad.processing.data import Upload


def get_upload_files(upload_id: str, user_id: str) -> StagingUploadFiles | None:
    """
    Retrieves files for an upload after verifying user authorization.

    Checks if the user is the main author or a coauthor.

    Args:
        upload_id: The unique identifier for the upload.
        user_id: The unique identifier for the user.

    Returns:
        The UploadFiles object if found and authorized, otherwise None
        (if the upload doesn't exist or the associated files aren't found).

    Raises:
        PermissionError: If the upload exists but the user is not authorized.
    """
    if infrastructure.mongo_client is None:
        infrastructure.setup_mongo()

    upload = Upload.get(upload_id)

    if upload is None:
        return None

    # Determine if user is authorized to get the upload.
    is_coauthor = isinstance(upload.coauthors, list) and user_id in upload.coauthors
    is_authorized = upload.main_author == user_id or is_coauthor

    # Raise error if not authorized
    if not is_authorized:
        raise PermissionError(
            f'User {user_id} is not authorized to access upload {upload_id}.'
        )

    # User is authorized, retrieve and return files
    if StagingUploadFiles.exists_for(upload_id):
        return StagingUploadFiles(upload_id)

    return None


def action_artifacts_dir() -> str:
    """
    Returns the path to the action artifacts directory.

    Activities can use this directory to store their artifacts.
    """
    path = os.path.join(config.fs.tmp, 'action_artifacts')
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path


def start_action(action_id: str, data: Any) -> str:
    """
    Starts a new Action with the given ID and input data.

    Args:
        action_id (str): The ID of the action to start. The action ID is the identifier of the
        action entry point as set in the `pyproject.toml` file.
        data (Any): Input data for the action. Must have a `user_id` attribute.
        The data type should be compatible with the type defined in the input data model.
        task_queue (TaskQueue): The task queue to use for action execution.

    Returns:
        str: The unique ID of the started action instance.
    """
    assert hasattr(data, 'user_id')
    user_id = data.user_id
    workflow_id = f'{action_id}-{user_id}-{uuid.uuid4()}'
    action = get_actions().get(action_id)
    assert action, f'No action data for the given {action_id} ID'

    async def async_start_workflow() -> str:
        client = await get_client()
        await client.start_workflow(
            action.workflow.run,
            data,
            id=workflow_id,
            task_queue=action.task_queue,
        )
        return workflow_id

    with ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, async_start_workflow())
        return future.result()


def get_action_status(action_instance_id: str) -> WorkflowExecutionStatus | None:
    """
    Retrieves the current execution status of an action ID.

    Args:
        action_instance_id (str): The unique ID of the action instance to check.

    Returns:
        WorkflowExecutionStatus | None: The current status of the action if found,
        or None if the action does not exist or cannot be described.
    """

    async def async_get_workflow_status():
        client = await get_client()
        handle = client.get_workflow_handle(action_instance_id)
        status = await handle.describe()
        return status.status

    with ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, async_get_workflow_status())
        return future.result()


def get_action_result(action_instance_id: str) -> Any | None:
    """
    Retrieves the current execution status of an action ID.

    This function is **blocking** and should only be called after confirming
    that the target workflow has finished execution. If called while the workflow
    is still running, it will block until the workflow completes.

    Args:
        action_instance_id (str): The unique ID of the action to check.

    Returns:
        Action result if found.
    """

    async def async_get_workflow_result():
        client = await get_client()
        handle = client.get_workflow_handle(action_instance_id)
        return await handle.result()

    with ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, async_get_workflow_result())
        return future.result()
