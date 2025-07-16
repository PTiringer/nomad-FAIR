import uuid

from temporalio import activity

from nomad.files import PublicUploadFiles, StagingUploadFiles
from nomad.parsing.parsers import parsers
from nomad.processing.base import ProcessStatus
from nomad.processing.data import Entry, Upload
from nomad.search import delete_upload
from nomad.workflows.shared_objects import (
    DeleteUploadWorkflowInput,
    EditUploadMetadataWorkflowInput,
    ImportBundleWorkflowInput,
    ProcessEntryActivityInput,
    ProcessExampleUploadWorkflowInput,
    PublishExternallyWorkflowInput,
    PublishUploadWorkflowInput,
    UploadProcessingWorkflowInput,
    UploadWorkflowIdInput,
)

parser_min_level = min([parser.level for parser in parsers])


@activity.defn
async def delete_upload_search_activity(input: DeleteUploadWorkflowInput):
    # Delete from search index
    delete_upload(input.upload_id, refresh=True)


@activity.defn
async def delete_upload_files_activity(input: DeleteUploadWorkflowInput):
    # Delete staging and public files
    for cls in (StagingUploadFiles, PublicUploadFiles):
        if cls.exists_for(input.upload_id):
            cls(input.upload_id).delete()


@activity.defn
async def delete_upload_entries_activity(input: DeleteUploadWorkflowInput):
    # Delete all entries for this upload
    Entry.objects(upload_id=input.upload_id).delete()  # type: ignore


@activity.defn
async def delete_upload_record_activity(input: DeleteUploadWorkflowInput):
    # Delete the upload itself
    upload = Upload.get(input.upload_id)
    upload.delete()


@activity.defn
async def process_entry_activity(input: ProcessEntryActivityInput):
    entry = Entry.get(input.entry_id)
    entry._process_entry_local()


@activity.defn
async def update_files_activity(
    input: UploadProcessingWorkflowInput,
) -> set[str] | None:
    upload = Upload.get(input.upload_id)
    file_operations = input.file_operations or []
    only_updated_files = (
        input.only_updated_files if input.only_updated_files is not None else False
    )
    updated_files = upload.update_files(file_operations, only_updated_files)

    return updated_files


@activity.defn
async def match_all_activity(input: UploadProcessingWorkflowInput):
    from nomad.config import config

    reprocess_settings = input.reprocess_settings or {}
    reprocess_obj = config.reprocess.customize(reprocess_settings)
    upload = Upload.get(input.upload_id)
    upload.match_all(
        reprocess_settings=reprocess_obj,
        path_filter=input.path_filter,
        updated_files=input.updated_files,
    )


@activity.defn
async def next_level_entries(
    input: UploadProcessingWorkflowInput,
) -> list[ProcessEntryActivityInput]:
    upload = Upload.get(input.upload_id)
    next_entries = upload.next_level_entries(
        min_level=input.min_level,
        path_filter=input.path_filter,
        updated_files=input.updated_files,
    )
    return [
        ProcessEntryActivityInput(
            upload_id=str(upload.upload_id),
            entry_id=str(entry.entry_id),
            workflow_id=f'process-entry-workflow-child-id-{entry.entry_id}-{upload.upload_id}-{uuid.uuid4()}',
        )
        for entry in next_entries
    ]


@activity.defn
async def add_workflow_id_activity(input: UploadWorkflowIdInput):
    upload = Upload.get(input.upload_id)
    assert len(upload.workflow_ids) == 0, (  # type: ignore
        'Upload is currently being processed by another workflow'
    )
    upload.workflow_ids.append(input.workflow_id)  # type: ignore
    upload.save()


@activity.defn
async def remove_workflow_id_activity(input: UploadWorkflowIdInput):
    upload = Upload.get(input.upload_id)
    upload.workflow_ids.remove(input.workflow_id)  # type: ignore
    upload.save()


@activity.defn
async def cleanup_activity(input: UploadProcessingWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload.cleanup()


@activity.defn
async def process_upload_success(input: UploadProcessingWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload.process_status = ProcessStatus.SUCCESS
    for entry in list(
        Entry.objects(upload_id=str(upload.upload_id), mainfile_key=None)  # type: ignore
    ):
        entry.process_status = ProcessStatus.SUCCESS
        entry.save()
    upload.set_last_status_message('Process completed successfully')


@activity.defn
async def setup_example_upload_activity(input: ProcessExampleUploadWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload.setup_example_upload(entry_point_id=input.example_upload_id)


def update_process_failure(workflow_type: str, input: dict, exception: Exception):
    if workflow_type == 'ProcessEntryWorkflow':
        entry_id = input['entry_id']
        entry = Entry.get(entry_id)
        entry.process_status = ProcessStatus.FAILURE
        entry.last_status_message = f'Process process_entry failed: {exception}'
        entry.save()

    if workflow_type == 'ProcessUploadWorkflow':
        upload_id = input['upload_id']
        upload = Upload.get(upload_id)
        upload.workflow_ids = []
        upload.process_status = ProcessStatus.FAILURE
        upload.last_status_message = f'Process upload failed: {exception}'
        upload.save()


@activity.defn
async def edit_upload_metadata_activity(input: EditUploadMetadataWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload._edit_upload_metadata_local(input.edit_request_json, input.user_id)


@activity.defn
async def import_bundle_activity(input: ImportBundleWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload._import_bundle_local(
        input.bundle_path, input.import_settings, input.embargo_length
    )


@activity.defn
async def publish_upload_activity(input: PublishUploadWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload._publish_upload_local(input.embargo_length)


@activity.defn
async def publish_externally_activity(input: PublishExternallyWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload._publish_externally_local()
