"""
All workflow class definitions for NOMAD workflows.
"""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from nomad.config import config
    from nomad.workflows.activities import (
        cleanup_activity,
        cleanup_workflow_tmp_dir_activity,
        delete_upload_entries_activity,
        delete_upload_files_activity,
        delete_upload_record_activity,
        delete_upload_search_activity,
        edit_upload_metadata_activity,
        get_entry_batch_from_file,
        handle_heartbeat_failure_activity,
        import_bundle_activity,
        match_all_activity,
        next_level_entries,
        parser_min_level,
        process_entry_activity,
        process_upload_failure_activity,
        process_upload_success,
        publish_externally_activity,
        publish_upload_activity,
        remove_workflow_id_activity,
        setup_example_upload_activity,
        setup_upload_for_workflow_process,
        update_files_activity,
    )
    from nomad.workflows.shared_objects import (
        DeleteUploadWorkflowInput,
        EditUploadMetadataWorkflowInput,
        EntriesToBeProcessedResult,
        EntryBatchFromFileInput,
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
        timeout = timedelta(
            seconds=config.temporal.processing_timeouts.delete_upload_timeout
        )
        heartbeat_timeout = timedelta(
            seconds=config.temporal.processing_timeouts.internal_processing_heartbeat_timeout
        )
        await workflow.execute_activity(
            delete_upload_search_activity,
            input,
            schedule_to_close_timeout=timeout,
            heartbeat_timeout=heartbeat_timeout,
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            delete_upload_files_activity,
            input,
            schedule_to_close_timeout=timeout,
            heartbeat_timeout=heartbeat_timeout,
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            delete_upload_entries_activity,
            input,
            schedule_to_close_timeout=timeout,
            heartbeat_timeout=heartbeat_timeout,
            retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            delete_upload_record_activity,
            input,
            schedule_to_close_timeout=timeout,
            heartbeat_timeout=heartbeat_timeout,
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
                schedule_to_close_timeout=timedelta(
                    seconds=config.temporal.processing_timeouts.process_entry_timeout
                ),
                heartbeat_timeout=timedelta(
                    seconds=config.temporal.processing_timeouts.internal_processing_heartbeat_timeout
                ),
                retry_policy=retry_policy,
            )
        except ActivityError as e:
            if 'heartbeat timeout' in str(e.cause):
                await workflow.execute_activity(
                    handle_heartbeat_failure_activity,
                    input,
                    schedule_to_close_timeout=timedelta(
                        seconds=config.temporal.processing_timeouts.process_entry_timeout
                    ),
                )
            raise e

        return result


@workflow.defn
class BatchProcessEntriesWorkflow:
    """
    Handles processing of entry batches.

    Architecture:
    - Processes batches sequentially to prevent task queue overload
    - Within each batch, processes up to 1000 entries concurrently
    - Handles both file-based storage (large datasets) and in-memory storage (small datasets)

    Note: 1000 is the limit set by Temporal for max number of child workflows.
    """

    @workflow.run
    async def run(self, next_level_entries_result: EntriesToBeProcessedResult):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        timeout = timedelta(
            seconds=config.temporal.processing_timeouts.process_upload_timeout
        )

        # Handle file-based entry storage (used for very large uploads)
        # Entries are stored in batch files to avoid memory constraints
        if entry_batch_directory := next_level_entries_result.directory:
            # Process each file-based batch sequentially to prevent overwhelming the task queue
            # Each batch will internally process up to 1000 entries concurrently
            for batch_id in range(next_level_entries_result.total_batches):
                # Load entries from the batch file
                entries_to_be_processed = await workflow.execute_activity(
                    get_entry_batch_from_file,
                    EntryBatchFromFileInput(
                        upload_id=next_level_entries_result.upload_id,
                        batch_dir_path=entry_batch_directory,
                        batch_id=batch_id,
                    ),
                    schedule_to_close_timeout=timedelta(
                        seconds=config.temporal.processing_timeouts.next_level_entries_timeout
                    ),
                    retry_policy=retry_policy,
                )

                # Recursively process this batch (which may further subdivide if >1000 entries)
                await workflow.execute_child_workflow(
                    BatchProcessEntriesWorkflow.run,
                    EntriesToBeProcessedResult(
                        entries=entries_to_be_processed,
                        upload_id=next_level_entries_result.upload_id,
                    ),
                    id=f'{workflow.info().workflow_id}-file-batch-{batch_id}',
                    parent_close_policy=workflow.ParentClosePolicy.TERMINATE,
                    retry_policy=retry_policy,
                )

        # Handle in-memory entry processing (from small uploads or loaded file batches)
        elif entries_to_be_processed := next_level_entries_result.entries:
            # Two-tier processing strategy based on batch size:
            # 1. Large batches (>1000): Split into smaller batches and process sequentially
            # 2. Small batches (≤1000): Process all entries concurrently
            if len(entries_to_be_processed) > 1000:
                entry_batches = generate_batches(entries_to_be_processed)
                # Each sub-batch will be processed with up to 1000 concurrent entries
                for i, batch in enumerate(entry_batches):
                    await workflow.execute_child_workflow(
                        BatchProcessEntriesWorkflow.run,
                        EntriesToBeProcessedResult(
                            entries=batch,
                            upload_id=next_level_entries_result.upload_id,
                        ),
                        id=f'{workflow.info().workflow_id}-batch-{i}',
                        retry_policy=retry_policy,
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
    """
    Specialized workflow to process an upload through multiple steps:
    1. Match all files to parsers
    2. Parse entries level by level
    3. Cleanup temporary data
    """

    @workflow.run
    async def run(self, input: UploadProcessingWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        heartbeat_timeout = timedelta(
            seconds=config.temporal.processing_timeouts.internal_processing_heartbeat_timeout
        )
        workflow_info = workflow.info()
        # Step 2: Match all, pass updated_files as set
        await workflow.execute_activity(
            match_all_activity,
            input,
            schedule_to_close_timeout=timedelta(
                seconds=config.temporal.processing_timeouts.match_all_timeout
            ),
            heartbeat_timeout=heartbeat_timeout,
            retry_policy=retry_policy,
        )

        # Step 3: Parse next level
        while True:  # Outer loop: Continue until no more parser levels to process
            next_level_entries_result = await workflow.execute_activity(
                next_level_entries,
                input,
                schedule_to_close_timeout=timedelta(
                    seconds=config.temporal.processing_timeouts.next_level_entries_timeout
                ),
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )

            # If None returned: no entries exist for this parser level at all
            # then we're done with all parser levels.
            if not next_level_entries_result:
                break

            # Delegate all batch processing complexity to BatchProcessEntriesWorkflow
            await workflow.execute_child_workflow(
                BatchProcessEntriesWorkflow.run,
                next_level_entries_result,
                id=f'{workflow_info.workflow_id}-{input.min_level}-batch-processor',
                parent_close_policy=workflow.ParentClosePolicy.TERMINATE,
                retry_policy=retry_policy,
            )

            next_parser_level = (
                next_level_entries_result.next_parser_level or input.min_level
            )
            input.min_level = next_parser_level + 1

        # Step 4: Cleanup
        await workflow.execute_activity(
            cleanup_activity,
            input,
            schedule_to_close_timeout=timedelta(
                seconds=config.temporal.processing_timeouts.cleanup_timeout
            ),
            heartbeat_timeout=heartbeat_timeout,
            retry_policy=retry_policy,
        )


@workflow.defn
class UpdateUploadWorkflow:
    """
    Workflow to update an upload's files and optionally reprocess them.
    1. Update files
    2. (Optional) Reprocess updated files through ProcessUploadWorkflow
    3. Mark upload as successful or failed
    By default, reprocessing is triggered unless specified otherwise.
    """

    @workflow.run
    async def run(self, input: UploadProcessingWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        timeout = timedelta(
            seconds=config.temporal.processing_timeouts.process_upload_timeout
        )
        heartbeat_timeout = timedelta(
            seconds=config.temporal.processing_timeouts.internal_processing_heartbeat_timeout
        )
        workflow_info = workflow.info()
        upload_workflow_input = UploadWorkflowIdInput(
            upload_id=input.upload_id,
            workflow_id=workflow_info.workflow_id,
            process_name='_process_upload',
            trigger_processing=input.trigger_processing,
        )
        try:
            # Step 0: Add workflow id to upload
            await workflow.execute_activity(
                setup_upload_for_workflow_process,
                upload_workflow_input,
                schedule_to_close_timeout=timedelta(
                    seconds=config.temporal.processing_timeouts.setup_upload_timeout
                ),
                retry_policy=retry_policy,
            )

            # Step 1: Update files
            updated_files = await workflow.execute_activity(
                update_files_activity,
                input,
                schedule_to_close_timeout=timedelta(
                    seconds=config.temporal.processing_timeouts.update_files_timeout
                ),
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )

            if input.trigger_processing:
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
                    workflow_tmp_dir=input.workflow_tmp_dir,
                )
                # Here we excecute steps:
                # 2: Match all, pass updated_files
                # 3: Parse next level(s)
                # 4: Cleanup
                await workflow.execute_child_workflow(
                    ProcessUploadWorkflow.run,
                    parse_all_input,
                    id=f'{workflow_info.workflow_id}-reprocess-{input.upload_id}',
                    parent_close_policy=workflow.ParentClosePolicy.TERMINATE,
                    retry_policy=retry_policy,
                )

            # Step 5: Mark as successful if the processing was triggered, otherwise will mark as READY
            await workflow.execute_activity(
                process_upload_success,
                upload_workflow_input,
                schedule_to_close_timeout=timedelta(
                    seconds=config.temporal.processing_timeouts.process_upload_success_timeout
                ),
                retry_policy=retry_policy,
            )

        except Exception as e:
            # Set upload to failure status
            upload_workflow_input.failure_message = 'Process upload failed'
            if isinstance(e, ActivityError):
                upload_workflow_input.error_details = str(e.cause)
            else:
                upload_workflow_input.error_details = str(e)

            await workflow.execute_activity(
                process_upload_failure_activity,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )
            raise e

        finally:
            # Always remove workflow id, even if processing failed
            await workflow.execute_activity(
                remove_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=timedelta(
                    seconds=config.temporal.processing_timeouts.remove_workflow_id_timeout
                ),
                retry_policy=retry_policy,
            )
            await workflow.execute_activity(
                cleanup_workflow_tmp_dir_activity,
                input.workflow_tmp_dir,
                schedule_to_close_timeout=timedelta(
                    seconds=config.temporal.processing_timeouts.cleanup_workflow_tmp_dir_timeout
                ),
                retry_policy=retry_policy,
            )


@workflow.defn
class ProcessExampleUploadWorkflow:
    @workflow.run
    async def run(self, input: ProcessExampleUploadWorkflowInput):
        # Step 1: Setup example upload
        timeout = timedelta(
            seconds=config.temporal.processing_timeouts.process_example_upload_timeout
        )
        heartbeat_timeout = timedelta(
            seconds=config.temporal.processing_timeouts.internal_processing_heartbeat_timeout
        )
        await workflow.execute_activity(
            setup_example_upload_activity,
            input,
            schedule_to_close_timeout=timeout,
            heartbeat_timeout=heartbeat_timeout,
        )
        current_workflow_id = workflow.info().workflow_id

        # Step 2: Process upload using the standard workflow
        process_upload_input = UploadProcessingWorkflowInput(
            upload_id=input.upload_id,
            file_operations=input.file_operations,
            publish_directly_after_processing=input.publish_directly,
            workflow_id=current_workflow_id,
            workflow_tmp_dir=input.workflow_tmp_dir,
        )

        await workflow.execute_child_workflow(
            UpdateUploadWorkflow.run,
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
        timeout = timedelta(
            seconds=config.temporal.processing_timeouts.edit_upload_metadata_timeout
        )
        heartbeat_timeout = timedelta(
            seconds=config.temporal.processing_timeouts.internal_processing_heartbeat_timeout
        )
        workflow_info = workflow.info()
        upload_workflow_input = UploadWorkflowIdInput(
            upload_id=input.upload_id,
            workflow_id=workflow_info.workflow_id,
            process_name='_edit_upload_metadata',
        )

        try:
            # Add workflow id to upload
            await workflow.execute_activity(
                setup_upload_for_workflow_process,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )

            # Edit upload metadata
            await workflow.execute_activity(
                edit_upload_metadata_activity,
                input,
                schedule_to_close_timeout=timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )

            # Mark as successful
            await workflow.execute_activity(
                process_upload_success,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )
        except Exception as e:
            # Set upload to failure status
            upload_workflow_input.failure_message = 'Edit metadata failed'
            if isinstance(e, ActivityError):
                upload_workflow_input.error_details = str(e.cause)
            else:
                upload_workflow_input.error_details = str(e)

            await workflow.execute_activity(
                process_upload_failure_activity,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )
            raise e

        finally:
            # Always remove workflow id, even if processing failed
            await workflow.execute_activity(
                remove_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )


@workflow.defn
class ImportBundleWorkflow:
    @workflow.run
    async def run(self, input: ImportBundleWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        timeout = timedelta(
            seconds=config.temporal.processing_timeouts.import_bundle_timeout
        )
        heartbeat_timeout = timedelta(
            seconds=config.temporal.processing_timeouts.internal_processing_heartbeat_timeout
        )
        workflow_info = workflow.info()
        upload_workflow_input = UploadWorkflowIdInput(
            upload_id=input.upload_id,
            workflow_id=workflow_info.workflow_id,
            process_name='_import_bundle',
        )

        try:
            # Add workflow id to upload
            await workflow.execute_activity(
                setup_upload_for_workflow_process,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )

            # Import bundle
            await workflow.execute_activity(
                import_bundle_activity,
                input,
                schedule_to_close_timeout=timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )

            # Mark as successful
            await workflow.execute_activity(
                process_upload_success,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )
        except Exception as e:
            # Set upload to failure status
            upload_workflow_input.failure_message = 'Import bundle failed'
            if isinstance(e, ActivityError):
                upload_workflow_input.error_details = str(e.cause)
            else:
                upload_workflow_input.error_details = str(e)

            await workflow.execute_activity(
                process_upload_failure_activity,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )
            raise e

        finally:
            # Always remove workflow id, even if processing failed
            await workflow.execute_activity(
                remove_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )


@workflow.defn
class PublishUploadWorkflow:
    @workflow.run
    async def run(self, input: PublishUploadWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        timeout = timedelta(
            seconds=config.temporal.processing_timeouts.publish_upload_timeout
        )
        heartbeat_timeout = timedelta(
            seconds=config.temporal.processing_timeouts.internal_processing_heartbeat_timeout
        )
        workflow_info = workflow.info()
        upload_workflow_input = UploadWorkflowIdInput(
            upload_id=input.upload_id,
            workflow_id=workflow_info.workflow_id,
            process_name='_publish_upload',
        )

        try:
            # Add workflow id to upload
            await workflow.execute_activity(
                setup_upload_for_workflow_process,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )

            # Publish upload
            await workflow.execute_activity(
                publish_upload_activity,
                input,
                schedule_to_close_timeout=timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )

            # Mark as successful
            await workflow.execute_activity(
                process_upload_success,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )

        except Exception as e:
            # Set upload to failure status
            upload_workflow_input.failure_message = 'Publish upload failed'
            if isinstance(e, ActivityError):
                upload_workflow_input.error_details = str(e.cause)
            else:
                upload_workflow_input.error_details = str(e)

            await workflow.execute_activity(
                process_upload_failure_activity,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )
            raise e

        finally:
            # Always remove workflow id, even if processing failed
            await workflow.execute_activity(
                remove_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )


@workflow.defn
class PublishExternallyWorkflow:
    @workflow.run
    async def run(self, input: PublishExternallyWorkflowInput):
        retry_policy = RetryPolicy(
            maximum_attempts=3,
        )
        timeout = timedelta(
            seconds=config.temporal.processing_timeouts.publish_externally_timeout
        )
        heartbeat_timeout = timedelta(
            seconds=config.temporal.processing_timeouts.internal_processing_heartbeat_timeout
        )
        workflow_info = workflow.info()
        upload_workflow_input = UploadWorkflowIdInput(
            upload_id=input.upload_id,
            workflow_id=workflow_info.workflow_id,
            process_name='_publish_externally',
        )

        try:
            # Add workflow id to upload
            await workflow.execute_activity(
                setup_upload_for_workflow_process,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )

            # Publish externally
            await workflow.execute_activity(
                publish_externally_activity,
                input,
                schedule_to_close_timeout=timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )

            # Mark as successful
            await workflow.execute_activity(
                process_upload_success,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )

        except Exception as e:
            # Set upload to failure status
            upload_workflow_input.failure_message = 'Publish externally failed'
            if isinstance(e, ActivityError):
                upload_workflow_input.error_details = str(e.cause)
            else:
                upload_workflow_input.error_details = str(e)

            await workflow.execute_activity(
                process_upload_failure_activity,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )
            raise e

        finally:
            # Always remove workflow id, even if processing failed
            await workflow.execute_activity(
                remove_workflow_id_activity,
                upload_workflow_input,
                schedule_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )
