import asyncio
import signal
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from temporalio.worker import Worker

from nomad.actions import TaskQueue
from nomad.actions.activities.utils import get_all_activities
from nomad.actions.client import get_client
from nomad.actions.workflows.utils import get_all_workflows
from nomad.config import config
from nomad.infrastructure import setup
from nomad.utils.structlogging import get_logger


async def run_worker(workers: int = 12):
    logger = get_logger(__name__)
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler():
        # Handle graceful shutdown
        logger.info('Received SIGTERM. Preparing for graceful shutdown')
        stop_event.set()

    loop.add_signal_handler(signal.SIGTERM, _signal_handler)
    loop.add_signal_handler(signal.SIGINT, _signal_handler)

    client = await get_client()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        worker = Worker(
            client,
            task_queue=TaskQueue.GPU.value,
            workflows=get_all_workflows(TaskQueue.GPU),
            activities=get_all_activities(TaskQueue.GPU),
            activity_executor=executor,
            graceful_shutdown_timeout=timedelta(
                seconds=config.temporal.graceful_shutdown_timeout
            ),
            # Limit the number of concurrent activities to avoid overloading the worker
            max_concurrent_activities=workers,
        )
        setup()
        # Run the worker until SIGTERM
        logger.info('Starting GPU worker.')
        worker_task = asyncio.create_task(worker.run())
        await stop_event.wait()

        logger.info('Stopping worker.')
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            logger.info('Worker shut down cleanly.')


def main(workers: int = 12):
    asyncio.run(run_worker(workers=workers))


if __name__ == '__main__':
    main()
