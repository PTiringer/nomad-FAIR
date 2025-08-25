from typing import Any

from nomad.orchestrator.shared.constant import TaskQueue
from nomad.workflows.workflows import (
    BatchProcessEntriesWorkflow,
    DeleteUploadWorkflow,
    EditUploadMetadataWorkflow,
    ImportBundleWorkflow,
    ProcessEntryWorkflow,
    ProcessExampleUploadWorkflow,
    ProcessUploadWorkflow,
    PublishExternallyWorkflow,
    PublishUploadWorkflow,
)


def get_nomad_internal_workflows() -> list:
    return [
        BatchProcessEntriesWorkflow,
        DeleteUploadWorkflow,
        ProcessUploadWorkflow,
        ProcessEntryWorkflow,
        ProcessExampleUploadWorkflow,
        EditUploadMetadataWorkflow,
        ImportBundleWorkflow,
        PublishUploadWorkflow,
        PublishExternallyWorkflow,
    ]


def get_all_workflows(task_queue: TaskQueue) -> list:
    workflows: list[Any] = []

    if task_queue == TaskQueue.NOMAD_INTERNAL_WORKFLOWS:
        workflows.extend(get_nomad_internal_workflows())

    return workflows
