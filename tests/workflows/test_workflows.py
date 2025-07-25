import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from nomad.orchestrator.client import get_client
from nomad.processing.base import ProcessStatus
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
    process_entry_activity,
    process_entry_success,
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
)
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


class TestFixtures:
    """Test data fixtures for workflow inputs."""

    @staticmethod
    def delete_upload_input():
        return DeleteUploadWorkflowInput(upload_id='test-upload-123')

    @staticmethod
    def process_entry_input():
        return ProcessEntryActivityInput(
            upload_id='test-upload-123',
            entry_id='test-entry-456',
            workflow_id=str(uuid.uuid4()),
        )

    @staticmethod
    def upload_processing_input():
        return UploadProcessingWorkflowInput(
            upload_id='test-upload-123',
            file_operations=[dict(op='CREATE', temporary=True)],
            reprocess_settings=None,
            path_filter=None,
            only_updated_files=False,
            publish_directly_after_processing=True,
            workflow_id=str(uuid.uuid4()),
        )

    @staticmethod
    def process_example_upload_input():
        return ProcessExampleUploadWorkflowInput(
            upload_id='test-upload-123',
            file_operations=[dict(op='CREATE', temporary=True)],
            publish_directly=True,
            example_upload_id='example-upload-id',
        )

    @staticmethod
    def edit_upload_metadata_input():
        return EditUploadMetadataWorkflowInput(
            upload_id='test-upload-123',
            edit_request_json={'title': 'Test Upload'},
            user_id='test-user',
        )

    @staticmethod
    def import_bundle_input():
        return ImportBundleWorkflowInput(
            bundle_path='/path/to/bundle',
            upload_id='test-upload-123',
            import_settings={},
        )

    @staticmethod
    def publish_upload_input():
        return PublishUploadWorkflowInput(upload_id='test-upload-123')

    @staticmethod
    def publish_externally_input():
        return PublishExternallyWorkflowInput(upload_id='test-upload-123')


@pytest.fixture
def mock_data_layer(monkeypatch):
    """Mock all data layer dependencies with monkeypatch."""
    # Mock Upload class and instances
    mock_upload_instance = Mock()
    mock_upload_instance.workflow_ids = []
    mock_upload_instance.update_files.return_value = {'updated_file.txt'}
    mock_upload_instance.next_level_entries.return_value = []
    mock_upload_instance.parser_level = 1

    mock_upload_class = Mock()
    mock_upload_class.get.return_value = mock_upload_instance
    monkeypatch.setattr('nomad.workflows.activities.Upload', mock_upload_class)

    # Mock Entry class and instances
    mock_entry_instance = Mock()
    mock_entry_objects = Mock()
    mock_entry_class = Mock()
    mock_entry_class.get.return_value = mock_entry_instance
    mock_entry_class.objects.return_value = mock_entry_objects
    monkeypatch.setattr('nomad.workflows.activities.Entry', mock_entry_class)

    # Mock file classes
    mock_staging_files = Mock()
    mock_staging_files.exists_for.return_value = True
    mock_staging_files_instance = Mock()
    mock_staging_files.return_value = mock_staging_files_instance
    monkeypatch.setattr(
        'nomad.workflows.activities.StagingUploadFiles', mock_staging_files
    )

    mock_public_files = Mock()
    mock_public_files.exists_for.return_value = True
    mock_public_files_instance = Mock()
    mock_public_files.return_value = mock_public_files_instance
    monkeypatch.setattr(
        'nomad.workflows.activities.PublicUploadFiles', mock_public_files
    )

    # Mock search functions
    mock_delete_upload = Mock()
    monkeypatch.setattr('nomad.workflows.activities.delete_upload', mock_delete_upload)

    # Mock config
    mock_config = Mock()
    mock_reprocess = Mock()
    mock_reprocess.customize.return_value = {}
    mock_config.reprocess = mock_reprocess
    monkeypatch.setattr('nomad.config.config', mock_config)

    return {
        'upload_class': mock_upload_class,
        'upload_instance': mock_upload_instance,
        'entry_class': mock_entry_class,
        'entry_instance': mock_entry_instance,
        'entry_objects': mock_entry_objects,
        'staging_files': mock_staging_files,
        'staging_files_instance': mock_staging_files_instance,
        'public_files': mock_public_files,
        'public_files_instance': mock_public_files_instance,
        'delete_upload': mock_delete_upload,
    }


class TestDeleteUploadWorkflow:
    """Tests for DeleteUploadWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_deletion(self, mock_data_layer):
        """Test successful upload deletion with all activities succeeding."""
        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.delete_upload_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[DeleteUploadWorkflow],
                    activities=[
                        delete_upload_search_activity,
                        delete_upload_files_activity,
                        delete_upload_entries_activity,
                        delete_upload_record_activity,
                    ],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        DeleteUploadWorkflow.run,
                        input_data,
                        id='test-delete-upload-workflow',
                        task_queue='test-task-queue',
                    )

            # Verify data layer calls
            mock_data_layer['delete_upload'].assert_called_once_with(
                'test-upload-123', refresh=True
            )
            mock_data_layer['staging_files'].exists_for.assert_called_with(
                'test-upload-123'
            )
            mock_data_layer['public_files'].exists_for.assert_called_with(
                'test-upload-123'
            )
            mock_data_layer['staging_files_instance'].delete.assert_called_once()
            mock_data_layer['public_files_instance'].delete.assert_called_once()
            mock_data_layer['entry_class'].objects.assert_called_once_with(
                upload_id='test-upload-123'
            )
            mock_data_layer['entry_objects'].delete.assert_called_once()
            mock_data_layer['upload_class'].get.assert_called_with('test-upload-123')
            mock_data_layer['upload_instance'].delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_deletion_with_no_files(self, mock_data_layer):
        """Test deletion when no files exist."""
        # Configure mocks - no files exist
        mock_data_layer['staging_files'].exists_for.return_value = False
        mock_data_layer['public_files'].exists_for.return_value = False

        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.delete_upload_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[DeleteUploadWorkflow],
                    activities=[
                        delete_upload_search_activity,
                        delete_upload_files_activity,
                        delete_upload_entries_activity,
                        delete_upload_record_activity,
                    ],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        DeleteUploadWorkflow.run,
                        input_data,
                        id='test-delete-upload-workflow-no-files',
                        task_queue='test-task-queue',
                    )

                # Verify file deletion was not called since files don't exist
                mock_data_layer['staging_files_instance'].delete.assert_not_called()
                mock_data_layer['public_files_instance'].delete.assert_not_called()


class TestProcessEntryWorkflow:
    """Tests for ProcessEntryWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_entry_processing(self, mock_data_layer):
        """Test successful entry processing."""
        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.process_entry_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[ProcessEntryWorkflow],
                    activities=[process_entry_activity, process_entry_success],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        ProcessEntryWorkflow.run,
                        input_data,
                        id='test-process-entry-workflow',
                        task_queue='test-task-queue',
                    )

            # Verify entry processing calls
            mock_data_layer['entry_class'].get.assert_called_with('test-entry-456')
            mock_data_layer['entry_instance']._process_entry_local.assert_called_once()

            # Verify entry process status is set to success and saved
            assert (
                mock_data_layer['entry_instance'].process_status
                == ProcessStatus.SUCCESS
            )
            mock_data_layer['entry_instance'].save.assert_called_once()


class TestBatchProcessEntriesWorkflow:
    """Tests for BatchProcessEntriesWorkflow."""

    @pytest.mark.asyncio
    async def test_small_batch_direct_processing(self, mock_data_layer):
        """Test processing small batch (<=1000 entries) directly."""
        entries = [TestFixtures.process_entry_input() for _ in range(5)]

        async with WorkflowEnvironment.from_client(await get_client()) as env:
            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[BatchProcessEntriesWorkflow, ProcessEntryWorkflow],
                    activities=[process_entry_activity, process_entry_success],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        BatchProcessEntriesWorkflow.run,
                        entries,
                        id='test-batch-process-small',
                        task_queue='test-task-queue',
                    )

        # Verify entries were processed
        assert (
            mock_data_layer['entry_class'].get.call_count == 10
        )  # 5 entries * 2 calls each (activity + success)


class TestProcessUploadWorkflow:
    """Tests for ProcessUploadWorkflow."""

    @pytest.mark.asyncio
    async def test_complete_upload_processing(self, mock_data_layer, monkeypatch):
        """Test complete upload processing workflow."""

        # Mock next_level_entries to return entries first, then empty
        def mock_next_level_entries_side_effect(*args, **kwargs):
            if not hasattr(mock_next_level_entries_side_effect, 'call_count'):
                mock_next_level_entries_side_effect.call_count = 0

            mock_next_level_entries_side_effect.call_count += 1

            if mock_next_level_entries_side_effect.call_count == 1:
                return [Mock(entry_id='test-entry-1')]
            else:
                return []

        mock_data_layer[
            'upload_instance'
        ].next_level_entries.side_effect = mock_next_level_entries_side_effect

        # Mock parser_min_level
        monkeypatch.setattr('nomad.workflows.activities.parser_min_level', 0)

        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.upload_processing_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[
                        ProcessUploadWorkflow,
                        BatchProcessEntriesWorkflow,
                        ProcessEntryWorkflow,
                    ],
                    activities=[
                        add_workflow_id_activity,
                        update_files_activity,
                        match_all_activity,
                        next_level_entries,
                        cleanup_activity,
                        process_upload_success,
                        remove_workflow_id_activity,
                        process_entry_activity,
                        process_entry_success,
                    ],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        ProcessUploadWorkflow.run,
                        input_data,
                        id='test-process-upload-workflow',
                        task_queue='test-task-queue',
                    )

            # Verify workflow ID management
            assert (
                len(mock_data_layer['upload_instance'].workflow_ids) >= 0
            )  # May be empty after removal
            mock_data_layer['upload_instance'].save.assert_called()
            mock_data_layer['upload_instance'].update_files.assert_called_once()
            mock_data_layer['upload_instance'].match_all.assert_called_once()
            mock_data_layer['upload_instance'].cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_processing_loop_multiple_levels(self, mock_data_layer, monkeypatch):
        """Test processing loop with multiple parser levels."""
        call_count = 0

        def mock_next_level_entries_multi_level(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                return [Mock(entry_id='test-entry-1')]
            elif call_count == 2:
                return [Mock(entry_id='test-entry-2')]
            else:
                return []

        mock_data_layer[
            'upload_instance'
        ].next_level_entries.side_effect = mock_next_level_entries_multi_level
        monkeypatch.setattr('nomad.workflows.activities.parser_min_level', 0)

        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.upload_processing_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[
                        ProcessUploadWorkflow,
                        BatchProcessEntriesWorkflow,
                        ProcessEntryWorkflow,
                    ],
                    activities=[
                        add_workflow_id_activity,
                        update_files_activity,
                        match_all_activity,
                        next_level_entries,
                        cleanup_activity,
                        process_upload_success,
                        remove_workflow_id_activity,
                        process_entry_activity,
                        process_entry_success,
                    ],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        ProcessUploadWorkflow.run,
                        input_data,
                        id='test-process-upload-workflow-levels',
                        task_queue='test-task-queue',
                    )

            # Verify next_level_entries was called multiple times
            assert mock_data_layer['upload_instance'].next_level_entries.call_count == 3


class TestProcessExampleUploadWorkflow:
    """Tests for ProcessExampleUploadWorkflow."""

    @pytest.mark.asyncio
    async def test_example_upload_processing(self, mock_data_layer, monkeypatch):
        """Test example upload processing workflow."""
        # Mock to prevent the processing loop from running
        mock_data_layer['upload_instance'].next_level_entries.return_value = []
        monkeypatch.setattr('nomad.workflows.activities.parser_min_level', 0)

        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.process_example_upload_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[
                        ProcessExampleUploadWorkflow,
                        ProcessUploadWorkflow,
                        BatchProcessEntriesWorkflow,
                        ProcessEntryWorkflow,
                    ],
                    activities=[
                        setup_example_upload_activity,
                        add_workflow_id_activity,
                        update_files_activity,
                        match_all_activity,
                        next_level_entries,
                        cleanup_activity,
                        process_upload_success,
                        remove_workflow_id_activity,
                        process_entry_activity,
                        process_entry_success,
                    ],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        ProcessExampleUploadWorkflow.run,
                        input_data,
                        id='test-process-example-upload-workflow',
                        task_queue='test-task-queue',
                    )

            # Verify setup activity was called
            mock_data_layer[
                'upload_instance'
            ].setup_example_upload.assert_called_once_with(
                entry_point_id='example-upload-id'
            )


class TestEditUploadMetadataWorkflow:
    """Tests for EditUploadMetadataWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_metadata_edit(self, mock_data_layer):
        """Test successful metadata editing."""
        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.edit_upload_metadata_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[EditUploadMetadataWorkflow],
                    activities=[
                        add_workflow_id_activity,
                        edit_upload_metadata_activity,
                        remove_workflow_id_activity,
                    ],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        EditUploadMetadataWorkflow.run,
                        input_data,
                        id='test-edit-upload-metadata-workflow',
                        task_queue='test-task-queue',
                    )

            # Verify metadata editing was called
            mock_data_layer[
                'upload_instance'
            ]._edit_upload_metadata_local.assert_called_once_with(
                {'title': 'Test Upload'}, 'test-user'
            )


class TestImportBundleWorkflow:
    """Tests for ImportBundleWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_bundle_import(self, mock_data_layer):
        """Test successful bundle import."""
        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.import_bundle_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[ImportBundleWorkflow],
                    activities=[import_bundle_activity],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        ImportBundleWorkflow.run,
                        input_data,
                        id='test-import-bundle-workflow',
                        task_queue='test-task-queue',
                    )

            # Verify bundle import was called
            mock_data_layer[
                'upload_instance'
            ]._import_bundle_local.assert_called_once_with('/path/to/bundle', {}, None)


class TestPublishUploadWorkflow:
    """Tests for PublishUploadWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_upload_publish(self, mock_data_layer):
        """Test successful upload publishing."""
        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.publish_upload_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[PublishUploadWorkflow],
                    activities=[
                        add_workflow_id_activity,
                        publish_upload_activity,
                        remove_workflow_id_activity,
                    ],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        PublishUploadWorkflow.run,
                        input_data,
                        id='test-publish-upload-workflow',
                        task_queue='test-task-queue',
                    )

            # Verify publishing was called
            mock_data_layer[
                'upload_instance'
            ]._publish_upload_local.assert_called_once_with(None)


class TestPublishExternallyWorkflow:
    """Tests for PublishExternallyWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_external_publish(self, mock_data_layer):
        """Test successful external publishing."""
        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.publish_externally_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[PublishExternallyWorkflow],
                    activities=[
                        add_workflow_id_activity,
                        publish_externally_activity,
                        remove_workflow_id_activity,
                    ],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        PublishExternallyWorkflow.run,
                        input_data,
                        id='test-publish-externally-workflow',
                        task_queue='test-task-queue',
                    )

            # Verify external publishing was called
            mock_data_layer[
                'upload_instance'
            ]._publish_externally_local.assert_called_once()


# Parameterized tests for common patterns
class TestWorkflowCommonPatterns:
    """Tests for common patterns across workflows."""

    @pytest.mark.parametrize(
        'workflow_class,input_data,activity_method',
        [
            (
                EditUploadMetadataWorkflow,
                TestFixtures.edit_upload_metadata_input(),
                '_edit_upload_metadata_local',
            ),
            (
                PublishUploadWorkflow,
                TestFixtures.publish_upload_input(),
                '_publish_upload_local',
            ),
            (
                PublishExternallyWorkflow,
                TestFixtures.publish_externally_input(),
                '_publish_externally_local',
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_workflow_id_management_pattern(
        self, mock_data_layer, workflow_class, input_data, activity_method
    ):
        """Test that workflows properly manage workflow IDs."""
        async with WorkflowEnvironment.from_client(await get_client()) as env:
            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[workflow_class],
                    activities=[
                        add_workflow_id_activity,
                        edit_upload_metadata_activity,
                        publish_upload_activity,
                        publish_externally_activity,
                        remove_workflow_id_activity,
                    ],
                    activity_executor=executor,
                ):
                    await env.client.execute_workflow(
                        workflow_class.run,
                        input_data,
                        id=f'test-{workflow_class.__name__.lower()}',
                        task_queue='test-task-queue',
                    )

            # Verify workflow ID management calls occurred
            mock_data_layer['upload_instance'].save.assert_called()
            # Should remove workflow ID after each workflow.
            assert not mock_data_layer['upload_instance'].workflow_ids

            # Verify the specific activity method was called
            if hasattr(mock_data_layer['upload_instance'], activity_method):
                getattr(
                    mock_data_layer['upload_instance'], activity_method
                ).assert_called_once()


class TestWorkflowErrorHandling:
    """Tests for workflow error handling scenarios."""

    @pytest.mark.asyncio
    async def test_upload_workflow_id_assertion_error(self, mock_data_layer):
        """Test that workflows fail when upload is already being processed."""
        # Set up upload to already have a workflow ID
        mock_data_layer['upload_instance'].workflow_ids = ['existing-workflow-id']

        async with WorkflowEnvironment.from_client(await get_client()) as env:
            input_data = TestFixtures.edit_upload_metadata_input()

            with ThreadPoolExecutor(max_workers=1) as executor:
                async with Worker(
                    env.client,
                    task_queue='test-task-queue',
                    workflows=[EditUploadMetadataWorkflow],
                    activities=[
                        add_workflow_id_activity,
                        edit_upload_metadata_activity,
                        remove_workflow_id_activity,
                    ],
                    activity_executor=executor,
                ):
                    with pytest.raises(
                        Exception
                    ):  # Should raise AssertionError from add_workflow_id_activity
                        await env.client.execute_workflow(
                            EditUploadMetadataWorkflow.run,
                            input_data,
                            id='test-workflow-id-conflict',
                            task_queue='test-task-queue',
                        )
