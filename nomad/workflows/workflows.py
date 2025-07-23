"""
All workflow class definitions for NOMAD workflows.
"""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from nomad.workflows.activities import (
        add_workflow_id_activity,
        cleanup_activity,
        delete_upload_entries_activity,
        delete_upload_files_activity,
        delete_upload_record_activity,
        delete_upload_search_activity,
        edit_upload_metadata_activity,
        import_bundle_activity,
        match_all_activity,
        next_level_entries,
        parser_min_level,
        process_entry_activity,
        process_upload_success,
        publish_externally_activity,
        publish_upload_activity,
        remove_workflow_id_activity,
        setup_example_upload_activity,
        update_files_activity,
    )
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
    from nomad.workflows.utils import generate_batches


@workflow.defn
class DeleteUploadWorkflow:
    @workflow.run
    async def run(self, input: DeleteUploadWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        await workflow.execute_activity(
            delete_upload_search_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=2),
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            delete_upload_files_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=2),
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            delete_upload_entries_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=2),
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            delete_upload_record_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=2),
            retry_policy=retry_policy,
        )


@workflow.defn
class ProcessEntryWorkflow:
    @workflow.run
    async def run(self, input: ProcessEntryActivityInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        result = await workflow.execute_activity(
            process_entry_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=1),
            retry_policy=retry_policy,
        )
        return result


@workflow.defn
class BatchProcessEntriesWorkflow:
    @workflow.run
    async def run(self, entries_to_be_processed: list[ProcessEntryActivityInput]):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        if len(entries_to_be_processed) > 1000:
            entry_batches = generate_batches(entries_to_be_processed)
            # Recursively call BatchProcessEntriesWorkflow for each batch
            await asyncio.gather(
                *[
                    workflow.execute_child_workflow(
                        BatchProcessEntriesWorkflow.run,
                        batch,
                        id=f'{workflow.info().workflow_id}-batch-{i}',
                        retry_policy=retry_policy,
                    )
                    for i, batch in enumerate(entry_batches)
                ]
            )
        else:
            # Process entries directly when <= 1000
            tasks = [
                workflow.execute_child_workflow(
                    ProcessEntryWorkflow.run,
                    data,
                    id=data.workflow_id,
                    parent_close_policy=workflow.ParentClosePolicy.TERMINATE,
                    retry_policy=retry_policy,
                )
                for data in entries_to_be_processed
            ]
            await asyncio.gather(*tasks)


@workflow.defn
class ProcessUploadWorkflow:
    @workflow.run
    async def run(self, input: UploadProcessingWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        workflow_info = workflow.info()
        upload_workflow_input = UploadWorkflowIdInput(
            upload_id=input.upload_id, workflow_id=workflow_info.workflow_id
        )
        # Step 0: Add workflow id to upload
        await workflow.execute_activity(
            add_workflow_id_activity,
            upload_workflow_input,
            schedule_to_close_timeout=timedelta(hours=1),
            retry_policy=retry_policy,
        )
        # Step 1: Update files
        updated_files = await workflow.execute_activity(
            update_files_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=1),
            retry_policy=retry_policy,
        )

        # Step 2: Match all, pass updated_files as set
        parse_all_input = UploadProcessingWorkflowInput(
            upload_id=input.upload_id,
            file_operations=input.file_operations,
            reprocess_settings=input.reprocess_settings,
            path_filter=input.path_filter,
            only_updated_files=input.only_updated_files,
            publish_directly_after_processing=input.publish_directly_after_processing,
            updated_files=updated_files,
            min_level=parser_min_level,
            workflow_id=input.workflow_id,
        )
        await workflow.execute_activity(
            match_all_activity,
            parse_all_input,
            schedule_to_close_timeout=timedelta(hours=1),
            retry_policy=retry_policy,
        )

        # Step 3: Parse next level
        while True:
            next_level_entries_result = await workflow.execute_activity(
                next_level_entries,
                parse_all_input,
                schedule_to_close_timeout=timedelta(hours=2),
                retry_policy=retry_policy,
            )
            entries_to_be_processed = next_level_entries_result.entries_to_be_processed
            if not entries_to_be_processed:
                break

            # Step 4: Start the batch processing workflow
            await workflow.execute_child_workflow(
                BatchProcessEntriesWorkflow.run,
                entries_to_be_processed,
                id=f'{workflow_info.workflow_id}-batch-processor',
                parent_close_policy=workflow.ParentClosePolicy.TERMINATE,
                retry_policy=retry_policy,
            )
            parse_all_input.min_level = next_level_entries_result.next_parser_level + 1

        await workflow.execute_activity(
            cleanup_activity,
            input,
            schedule_to_close_timeout=timedelta(minutes=30),
            retry_policy=retry_policy,
        )

        await workflow.execute_activity(
            process_upload_success,
            input,
            schedule_to_close_timeout=timedelta(minutes=30),
            retry_policy=retry_policy,
        )

        await workflow.execute_activity(
            remove_workflow_id_activity,
            upload_workflow_input,
            schedule_to_close_timeout=timedelta(minutes=30),
            retry_policy=retry_policy,
        )


@workflow.defn
class ProcessExampleUploadWorkflow:
    @workflow.run
    async def run(self, input: ProcessExampleUploadWorkflowInput):
        # Step 1: Setup example upload
        await workflow.execute_activity(
            setup_example_upload_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=1),
        )
        current_workflow_id = workflow.info().workflow_id

        # Step 2: Process upload using the standard workflow
        process_upload_input = UploadProcessingWorkflowInput(
            upload_id=input.upload_id,
            file_operations=input.file_operations,
            publish_directly_after_processing=input.publish_directly,
            workflow_id=current_workflow_id,
        )

        await workflow.execute_child_workflow(
            ProcessUploadWorkflow.run,
            process_upload_input,
            id=f'process-upload-workflow-{current_workflow_id}-{input.upload_id}',
            parent_close_policy=workflow.ParentClosePolicy.TERMINATE,
        )


@workflow.defn
class EditUploadMetadataWorkflow:
    @workflow.run
    async def run(self, input: EditUploadMetadataWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        workflow_info = workflow.info()
        upload_workflow_input = UploadWorkflowIdInput(
            upload_id=input.upload_id, workflow_id=workflow_info.workflow_id
        )

        # Step 0: Add workflow id to upload
        await workflow.execute_activity(
            add_workflow_id_activity,
            upload_workflow_input,
            schedule_to_close_timeout=timedelta(hours=1),
            retry_policy=retry_policy,
        )
        # Step 1: Edit metadata activity
        await workflow.execute_activity(
            edit_upload_metadata_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=1),
            retry_policy=retry_policy,
        )
        # Step 2: Remove workflow id
        await workflow.execute_activity(
            remove_workflow_id_activity,
            upload_workflow_input,
            schedule_to_close_timeout=timedelta(minutes=30),
            retry_policy=retry_policy,
        )


@workflow.defn
class ImportBundleWorkflow:
    @workflow.run
    async def run(self, input: ImportBundleWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        await workflow.execute_activity(
            import_bundle_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=2),
            retry_policy=retry_policy,
        )


@workflow.defn
class PublishUploadWorkflow:
    @workflow.run
    async def run(self, input: PublishUploadWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        workflow_info = workflow.info()
        upload_workflow_input = UploadWorkflowIdInput(
            upload_id=input.upload_id, workflow_id=workflow_info.workflow_id
        )
        await workflow.execute_activity(
            add_workflow_id_activity,
            upload_workflow_input,
            schedule_to_close_timeout=timedelta(hours=1),
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            publish_upload_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=1),
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            remove_workflow_id_activity,
            upload_workflow_input,
            schedule_to_close_timeout=timedelta(minutes=30),
            retry_policy=retry_policy,
        )


@workflow.defn
class PublishExternallyWorkflow:
    @workflow.run
    async def run(self, input: PublishExternallyWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        workflow_info = workflow.info()
        upload_workflow_input = UploadWorkflowIdInput(
            upload_id=input.upload_id, workflow_id=workflow_info.workflow_id
        )
        await workflow.execute_activity(
            add_workflow_id_activity,
            upload_workflow_input,
            schedule_to_close_timeout=timedelta(hours=1),
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            publish_externally_activity,
            input,
            schedule_to_close_timeout=timedelta(hours=2),
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            remove_workflow_id_activity,
            upload_workflow_input,
            schedule_to_close_timeout=timedelta(minutes=30),
            retry_policy=retry_policy,
        )
