import concurrent.futures
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Interceptor, SharedStateManager, Worker

from nomad.actions import TaskQueue
from nomad.actions.activities.util import get_all_activities
from nomad.actions.workflows.util import get_all_workflows


def get_worker(
    client: Client,
    task_queue: TaskQueue,
    interceptors: list[Interceptor] | None = None,
    activity_executor: concurrent.futures.Executor | None = None,
    shared_state_manager: SharedStateManager | None = None,
    graceful_shutdown_timeout: timedelta = timedelta(),
):
    worker = Worker(
        client,
        task_queue=task_queue.value,
        workflows=get_all_workflows(task_queue),
        activities=get_all_activities(task_queue),
        interceptors=interceptors or [],
        activity_executor=activity_executor,
        shared_state_manager=shared_state_manager,
        graceful_shutdown_timeout=graceful_shutdown_timeout,
    )

    return worker
