import asyncio
from concurrent.futures import ThreadPoolExecutor

from nomad.actions import TaskQueue
from nomad.actions.client import get_client
from nomad.actions.workers.util import get_worker
from nomad.infrastructure import setup


async def run_worker():
    client = await get_client()
    with ThreadPoolExecutor(max_workers=12) as executor:
        worker = get_worker(
            client=client, task_queue=TaskQueue.CPU, activity_executor=executor
        )
        setup()
        await worker.run()


def main():
    asyncio.run(run_worker())


if __name__ == '__main__':
    main()
