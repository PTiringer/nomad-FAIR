import asyncio
from concurrent.futures import ThreadPoolExecutor

from nomad.actions import TaskQueue
from nomad.actions.client import get_client
from nomad.actions.workers.util import get_worker


async def run_worker():
    client = await get_client()
    # NOTE: internal processing is not thread safe, avoid increasing the number of workers.
    with ThreadPoolExecutor(max_workers=1) as executor:
        worker = get_worker(
            client=client,
            task_queue=TaskQueue.NOMAD_INTERNAL_WORKFLOWS,
            activity_executor=executor,
        )
        await worker.run()


def main():
    asyncio.run(run_worker())


if __name__ == '__main__':
    main()
