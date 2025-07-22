import concurrent.futures

from temporalio.client import Client
from temporalio.worker import Interceptor, Worker

from nomad.orchestrator.activities.util import get_all_activities
from nomad.orchestrator.shared.constant import TaskQueue
from nomad.orchestrator.workflows.util import get_all_workflows


def get_worker(
    client: Client,
    task_queue: TaskQueue,
    interceptors: list[Interceptor] | None = None,
    activity_executor: concurrent.futures.Executor | None = None,
):
    worker = Worker(
        client,
        task_queue=task_queue.value,
        workflows=get_all_workflows(task_queue),
        activities=get_all_activities(task_queue),
        interceptors=interceptors or [],
        activity_executor=activity_executor,
    )

    return worker
