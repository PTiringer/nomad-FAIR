"""
All workflow class definitions for NOMAD workflows.
"""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

WORKFLOW_TIMEOUT = timedelta(hours=4)

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
        process_entry_failure_activity,
        process_entry_success,
        process_upload_failure_activity,
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
            schedule_to_close_timeout=WORKFLOW_TIMEOUT,
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            delete_upload_files_activity,
            input,
            schedule_to_close_timeout=WORKFLOW_TIMEOUT,
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            delete_upload_entries_activity,
            input,
            schedule_to_close_timeout=WORKFLOW_TIMEOUT,
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            delete_upload_record_activity,
            input,
            schedule_to_close_timeout=WORKFLOW_TIMEOUT,
            retry_policy=retry_policy,
        )


@workflow.defn
class ProcessEntryWorkflow:
    @workflow.run
    async def run(self, input: ProcessEntryActivityInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )

        try:
            # Process the entry
            result = await workflow.execute_activity(
                process_entry_activity,
                input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Mark entry as successful
            await workflow.execute_activity(
                process_entry_success,
                input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            return result

        except Exception as e:
            # Set entry to failure status
            await workflow.execute_activity(
                process_entry_failure_activity,
                input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )
            raise e


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
            # Use return_exceptions=True to allow individual child workflows to fail
            # without stopping the entire batch or failing the parent workflow
            await asyncio.gather(*tasks, return_exceptions=True)


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

        try:
            # Step 0: Add workflow id to upload
            await workflow.execute_activity(
                add_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Step 1: Update files
            updated_files = await workflow.execute_activity(
                update_files_activity,
                input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
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
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Step 3: Parse next level
            while True:  # Outer loop: Continue until no more parser levels to process
                parse_all_input.batch_id = 0
                while True:  # Inner loop: Process all batches for the current parser level and current batch
                    next_level_entries_result = await workflow.execute_activity(
                        next_level_entries,
                        parse_all_input,
                        schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                        retry_policy=retry_policy,
                    )

                    # If None returned: no entries exist for this parser level at all
                    # then we're done with all parser levels.
                    # This breaks the inner loop and the outer loop
                    if not next_level_entries_result:
                        break

                    entries_to_be_processed = (
                        next_level_entries_result.entries_to_be_processed
                    )

                    # If empty array returned: no more batches for this parser level
                    # This breaks the inner loop and moves to next parser level
                    if not entries_to_be_processed:
                        break

                    # Step 4: Start the batch processing workflow for this batch
                    await workflow.execute_child_workflow(
                        BatchProcessEntriesWorkflow.run,
                        entries_to_be_processed,
                        id=f'{workflow_info.workflow_id}-{parse_all_input.min_level}-batch-processor',
                        parent_close_policy=workflow.ParentClosePolicy.TERMINATE,
                        retry_policy=retry_policy,
                    )

                    parse_all_input.batch_id += 1

                # If no entries existed for this parser level (None returned)
                # then we're done with all parser levels - break outer loop
                if not next_level_entries_result:
                    break

                next_parser_level = (
                    next_level_entries_result.next_parser_level
                    or parse_all_input.min_level
                )
                parse_all_input.min_level = next_parser_level + 1

            # Step 4: Cleanup
            await workflow.execute_activity(
                cleanup_activity,
                input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Step 5: Mark as successful
            await workflow.execute_activity(
                process_upload_success,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

        except Exception as e:
            # Set upload to failure status
            upload_workflow_input.failure_message = 'Process upload failed'
            await workflow.execute_activity(
                process_upload_failure_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )
            raise e

        finally:
            # Always remove workflow id, even if processing failed
            await workflow.execute_activity(
                remove_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
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
            schedule_to_close_timeout=WORKFLOW_TIMEOUT,
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

        try:
            # Add workflow id to upload
            await workflow.execute_activity(
                add_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Edit upload metadata
            await workflow.execute_activity(
                edit_upload_metadata_activity,
                input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Mark as successful
            await workflow.execute_activity(
                process_upload_success,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )
        except Exception as e:
            # Set upload to failure status
            upload_workflow_input.failure_message = 'Edit metadata failed'
            await workflow.execute_activity(
                process_upload_failure_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )
            raise e

        finally:
            # Always remove workflow id, even if processing failed
            await workflow.execute_activity(
                remove_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )


@workflow.defn
class ImportBundleWorkflow:
    @workflow.run
    async def run(self, input: ImportBundleWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        workflow_info = workflow.info()
        upload_workflow_input = UploadWorkflowIdInput(
            upload_id=input.upload_id, workflow_id=workflow_info.workflow_id
        )

        try:
            # Add workflow id to upload
            await workflow.execute_activity(
                add_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Import bundle
            await workflow.execute_activity(
                import_bundle_activity,
                input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Mark as successful
            await workflow.execute_activity(
                process_upload_success,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )
        except Exception as e:
            # Set upload to failure status
            upload_workflow_input.failure_message = 'Import bundle failed'
            await workflow.execute_activity(
                process_upload_failure_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )
            raise e

        finally:
            # Always remove workflow id, even if processing failed
            await workflow.execute_activity(
                remove_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
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

        try:
            # Add workflow id to upload
            await workflow.execute_activity(
                add_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Publish upload
            await workflow.execute_activity(
                publish_upload_activity,
                input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Mark as successful
            await workflow.execute_activity(
                process_upload_success,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

        except Exception as e:
            # Set upload to failure status
            upload_workflow_input.failure_message = 'Publish upload failed'
            await workflow.execute_activity(
                process_upload_failure_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )
            raise e

        finally:
            # Always remove workflow id, even if processing failed
            await workflow.execute_activity(
                remove_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
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

        try:
            # Add workflow id to upload
            await workflow.execute_activity(
                add_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Publish externally
            await workflow.execute_activity(
                publish_externally_activity,
                input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

            # Mark as successful
            await workflow.execute_activity(
                process_upload_success,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )

        except Exception as e:
            # Set upload to failure status
            upload_workflow_input.failure_message = 'Publish externally failed'
            await workflow.execute_activity(
                process_upload_failure_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )
            raise e

        finally:
            # Always remove workflow id, even if processing failed
            await workflow.execute_activity(
                remove_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=WORKFLOW_TIMEOUT,
                retry_policy=retry_policy,
            )
