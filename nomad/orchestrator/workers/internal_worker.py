import asyncio
from concurrent.futures import ThreadPoolExecutor

from nomad.infrastructure import setup
from nomad.orchestrator.client import get_client
from nomad.orchestrator.shared.constant import TaskQueue
from nomad.orchestrator.workers.util import get_worker


async def run_worker(workers: int = 12):
    client = await get_client()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        worker = get_worker(
            client=client,
            task_queue=TaskQueue.NOMAD_INTERNAL_WORKFLOWS,
            activity_executor=executor,
        )
        setup()
        await worker.run()


def main():
    asyncio.run(run_worker())


if __name__ == '__main__':
    main()
