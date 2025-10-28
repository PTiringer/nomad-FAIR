import asyncio
import multiprocessing
import signal
from concurrent.futures.process import ProcessPoolExecutor
from datetime import timedelta

from temporalio.worker import SharedStateManager

from nomad.actions import TaskQueue
from nomad.actions.client import get_client
from nomad.actions.workers.util import get_worker
from nomad.config import config
from nomad.infrastructure import setup
from nomad.utils.structlogging import get_logger


async def run_worker(workers: int):
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

    # NOTE: internal processing is not thread safe, avoid using ThreadPoolExecutor with more than 1 worker.
    with ProcessPoolExecutor(max_workers=workers, initializer=setup) as executor:
        worker = get_worker(
            client=client,
            task_queue=TaskQueue.NOMAD_INTERNAL_WORKFLOWS,
            activity_executor=executor,
            shared_state_manager=SharedStateManager.create_from_multiprocessing(
                multiprocessing.Manager()
            ),
            graceful_shutdown_timeout=timedelta(
                seconds=config.temporal.graceful_shutdown_timeout
            ),
        )

        # Run the worker until SIGTERM
        logger.info('Starting internal processing worker.')
        worker_task = asyncio.create_task(worker.run())
        await stop_event.wait()

        logger.info('Stopping worker.')
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            logger.info('Worker shut down cleanly.')


def main():
    asyncio.run(run_worker(1))


if __name__ == '__main__':
    main()
