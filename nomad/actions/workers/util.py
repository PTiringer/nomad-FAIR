import concurrent.futures

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
):
    worker = Worker(
        client,
        task_queue=task_queue.value,
        workflows=get_all_workflows(task_queue),
        activities=get_all_activities(task_queue),
        interceptors=interceptors or [],
        activity_executor=activity_executor,
        shared_state_manager=shared_state_manager,
    )

    return worker
