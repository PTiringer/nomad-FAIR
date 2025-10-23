import asyncio
import multiprocessing
from concurrent.futures.process import ProcessPoolExecutor

from temporalio.worker import SharedStateManager

from nomad.actions import TaskQueue
from nomad.actions.client import get_client
from nomad.actions.workers.util import get_worker
from nomad.infrastructure import setup


async def run_worker(workers: int):
    client = await get_client()
    # NOTE: internal processing is not thread safe, avoid increasing using ThreadPoolExecutor with more than 1 worker.
    with ProcessPoolExecutor(max_workers=workers, initializer=setup) as executor:
        worker = get_worker(
            client=client,
            task_queue=TaskQueue.NOMAD_INTERNAL_WORKFLOWS,
            activity_executor=executor,
            shared_state_manager=SharedStateManager.create_from_multiprocessing(
                multiprocessing.Manager()
            ),
        )
        await worker.run()


def main():
    asyncio.run(run_worker(1))


if __name__ == '__main__':
    main()
