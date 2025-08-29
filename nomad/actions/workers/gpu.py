import asyncio

from nomad.actions import TaskQueue
from nomad.actions.client import get_client
from nomad.actions.workers.util import get_worker


async def run_worker():
    client = await get_client()
    worker = get_worker(client=client, task_queue=TaskQueue.GPU)
    await worker.run()


def main():
    asyncio.run(run_worker())


if __name__ == '__main__':
    main()
