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
    NextLevelEntryResult,
    ProcessEntryActivityInput,
    ProcessExampleUploadWorkflowInput,
    PublishExternallyWorkflowInput,
    PublishUploadWorkflowInput,
    UploadProcessingWorkflowInput,
    UploadWorkflowIdInput,
)
from nomad.workflows.utils import generate_batches

parser_min_level = min([parser.level for parser in parsers])


@activity.defn
def delete_upload_search_activity(input: DeleteUploadWorkflowInput):
    # Delete from search index
    delete_upload(input.upload_id, refresh=True)


@activity.defn
def delete_upload_files_activity(input: DeleteUploadWorkflowInput):
    # Delete staging and public files
    for cls in (StagingUploadFiles, PublicUploadFiles):
        if cls.exists_for(input.upload_id):
            cls(input.upload_id).delete()


@activity.defn
def delete_upload_entries_activity(input: DeleteUploadWorkflowInput):
    # Delete all entries for this upload
    Entry.objects(upload_id=input.upload_id).delete()  # type: ignore


@activity.defn
def delete_upload_record_activity(input: DeleteUploadWorkflowInput):
    # Delete the upload itself
    upload = Upload.get(input.upload_id)
    upload.delete()


@activity.defn
def process_entry_activity(input: ProcessEntryActivityInput):
    entry = Entry.get(input.entry_id)
    entry._process_entry_local()


@activity.defn
def update_files_activity(
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
def match_all_activity(input: UploadProcessingWorkflowInput):
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
def next_level_entries(
    input: UploadProcessingWorkflowInput,
) -> NextLevelEntryResult | None:
    upload = Upload.get(input.upload_id)
    next_entries = upload.next_level_entries(
        min_level=input.min_level,
        path_filter=input.path_filter,
        updated_files=input.updated_files,
    )

    # If no entries exist at this parser level, return None
    # This signals the workflow that we're completely done (no more parser levels)
    if not next_entries:
        return None

    # Split all entries into manageable batches
    # Temporal imposes a limit of 1.5MB for the serialized result, this helps us stay within those limits.
    entry_batches = generate_batches(next_entries)

    # Check if the requested batch_id exists
    if len(entry_batches) <= input.batch_id:
        # No more batches for this parser level - return empty entries
        # This signals the workflow to move to the next parser level
        next_entries = []
    else:
        # Get the specific batch requested
        next_entries = entry_batches[input.batch_id]

    # Return the result with the batch (or empty list if no more batches)
    return NextLevelEntryResult(
        next_parser_level=upload.parser_level,
        entries_to_be_processed=[
            ProcessEntryActivityInput(
                upload_id=input.upload_id,
                entry_id=str(entry.entry_id),
                workflow_id=f'process-entry-workflow-child-id-{str(entry.entry_id)}-{str(upload.upload_id)}-{uuid.uuid4()}',
            )
            for entry in next_entries  # This will be empty if no more batches
        ],
    )


@activity.defn
def add_workflow_id_activity(input: UploadWorkflowIdInput):
    upload = Upload.get(input.upload_id)
    assert len(upload.workflow_ids) == 0, (  # type: ignore
        'Upload is currently being processed by another workflow'
    )
    upload.workflow_ids.append(input.workflow_id)  # type: ignore
    upload.save()


@activity.defn
def remove_workflow_id_activity(input: UploadWorkflowIdInput):
    upload = Upload.get(input.upload_id)
    if input.workflow_id in upload.workflow_ids:  # type: ignore
        upload.workflow_ids.remove(input.workflow_id)  # type: ignore
    upload.save()


@activity.defn
def cleanup_activity(input: UploadProcessingWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload.cleanup()


@activity.defn
def process_entry_success(input: ProcessEntryActivityInput):
    entry = Entry.get(input.entry_id)
    entry.process_status = ProcessStatus.SUCCESS
    entry.save()


@activity.defn
def process_upload_success(input: UploadWorkflowIdInput):
    upload = Upload.get(input.upload_id)
    upload.process_status = ProcessStatus.SUCCESS
    upload.set_last_status_message('Process completed successfully')


@activity.defn
def process_entry_failure_activity(input: ProcessEntryActivityInput):
    entry = Entry.get(input.entry_id)
    entry.process_status = ProcessStatus.FAILURE
    entry.last_status_message = 'Process process_entry failed'
    entry.save()


@activity.defn
def process_upload_failure_activity(input: UploadWorkflowIdInput):
    upload = Upload.get(input.upload_id)
    upload.process_status = ProcessStatus.FAILURE
    upload.last_status_message = (
        input.failure_message if input.failure_message else 'Process upload failed'
    )
    upload.workflow_ids = []  # Clear workflow IDs on failure
    upload.save()


@activity.defn
def setup_example_upload_activity(input: ProcessExampleUploadWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload.setup_example_upload(entry_point_id=input.example_upload_id)


@activity.defn
def edit_upload_metadata_activity(input: EditUploadMetadataWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload._edit_upload_metadata_local(input.edit_request_json, input.user_id)


@activity.defn
def import_bundle_activity(input: ImportBundleWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload._import_bundle_local(
        input.bundle_path, input.import_settings, input.embargo_length
    )


@activity.defn
def publish_upload_activity(input: PublishUploadWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload._publish_upload_local(input.embargo_length)


@activity.defn
def publish_externally_activity(input: PublishExternallyWorkflowInput):
    upload = Upload.get(input.upload_id)
    upload._publish_externally_local()
