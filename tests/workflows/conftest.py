from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from nomad.orchestrator.activities.util import get_nomad_internal_activities
from nomad.orchestrator.workflows.util import get_nomad_internal_workflows
from nomad.workflows import workflows


@pytest.fixture
def temporal_test_queue():
    return 'TESTS-QUEUE'


@pytest.fixture
def temporal_worker(temporal_test_queue, temporal_proc_infra, monkeypatch):
    temporal_activities = get_nomad_internal_activities()
    temporal_workflows = get_nomad_internal_workflows()

    # Much smaller timeout for tests.
    monkeypatch.setattr(workflows, 'WORKFLOW_TIMEOUT', timedelta(seconds=120))

    @asynccontextmanager
    async def worker_context():
        async with await WorkflowEnvironment.start_local() as env:
            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue=temporal_test_queue,
                    workflows=temporal_workflows,
                    activities=temporal_activities,
                    activity_executor=executor,
                ):
                    yield env

    return worker_context
