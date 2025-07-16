import asyncio

from nomad.infrastructure import setup
from nomad.orchestrator.client import get_client
from nomad.orchestrator.shared.constant import TaskQueue
from nomad.orchestrator.workers.util import get_worker
from nomad.workflows.interceptor import NomadTemporalInterceptor


async def run_worker():
    client = await get_client()
    worker = get_worker(
        client=client,
        task_queue=TaskQueue.NOMAD_INTERNAL_WORKFLOWS,
        interceptors=[NomadTemporalInterceptor()],
    )
    setup()
    await worker.run()


def main():
    asyncio.run(run_worker())


if __name__ == '__main__':
    main()
