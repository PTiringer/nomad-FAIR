import uuid
from unittest.mock import MagicMock, Mock

import pytest

from nomad.processing.base import ProcessStatus
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

# Test Constants
TEST_UPLOAD_ID = 'test-upload-123'
TEST_ENTRY_ID = 'test-entry-456'
TEST_USER_ID = 'test-user'
TEST_EXAMPLE_UPLOAD_ID = 'example-upload-id'
TEST_BUNDLE_PATH = '/path/to/bundle'
EXISTING_WORKFLOW_ID = 'existing-workflow-id'


class TestFixtures:
    """Test data fixtures for workflow inputs."""

    @staticmethod
    def delete_upload_input():
        return DeleteUploadWorkflowInput(upload_id=TEST_UPLOAD_ID)

    @staticmethod
    def process_entry_input():
        return ProcessEntryActivityInput(
            upload_id=TEST_UPLOAD_ID,
            entry_id=TEST_ENTRY_ID,
            workflow_id=str(uuid.uuid4()),
        )

    @staticmethod
    def upload_processing_input():
        return UploadProcessingWorkflowInput(
            upload_id=TEST_UPLOAD_ID,
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
            upload_id=TEST_UPLOAD_ID,
            file_operations=[dict(op='CREATE', temporary=True)],
            publish_directly=True,
            example_upload_id=TEST_EXAMPLE_UPLOAD_ID,
        )

    @staticmethod
    def edit_upload_metadata_input():
        return EditUploadMetadataWorkflowInput(
            upload_id=TEST_UPLOAD_ID,
            edit_request_json={'title': 'Test Upload'},
            user_id=TEST_USER_ID,
        )

    @staticmethod
    def import_bundle_input():
        return ImportBundleWorkflowInput(
            bundle_path=TEST_BUNDLE_PATH,
            upload_id=TEST_UPLOAD_ID,
            import_settings={},
        )

    @staticmethod
    def publish_upload_input():
        return PublishUploadWorkflowInput(upload_id=TEST_UPLOAD_ID)

    @staticmethod
    def publish_externally_input():
        return PublishExternallyWorkflowInput(upload_id=TEST_UPLOAD_ID)


@pytest.fixture
def mock_data_layer(monkeypatch):
    """Mock all data layer dependencies with monkeypatch."""
    # Mock Upload class and instances
    mock_upload_instance = MagicMock()
    mock_upload_instance.workflow_ids = []
    mock_upload_instance.update_files.return_value = {'updated_file.txt'}
    mock_upload_instance.next_level_entries.return_value = []
    mock_upload_instance.parser_level = 1

    mock_upload_class = Mock()
    mock_upload_class.get.return_value = mock_upload_instance
    monkeypatch.setattr('nomad.workflows.activities.Upload', mock_upload_class)

    # Mock Entry class and instances
    mock_entry_instance = MagicMock()
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
    async def test_successful_deletion(
        self, mock_data_layer, temporal_worker, temporal_test_queue
    ):
        """Test successful upload deletion with all activities succeeding."""
        async with temporal_worker() as env:
            input_data = TestFixtures.delete_upload_input()

            await env.client.execute_workflow(
                'DeleteUploadWorkflow',
                input_data,
                id='test-delete-upload-workflow',
                task_queue=temporal_test_queue,
            )

            # Verify data layer calls
            mock_data_layer['delete_upload'].assert_called_once_with(
                TEST_UPLOAD_ID, refresh=True
            )
            mock_data_layer['staging_files'].exists_for.assert_called_with(
                TEST_UPLOAD_ID
            )
            mock_data_layer['public_files'].exists_for.assert_called_with(
                TEST_UPLOAD_ID
            )
            mock_data_layer['staging_files_instance'].delete.assert_called_once()
            mock_data_layer['public_files_instance'].delete.assert_called_once()
            mock_data_layer['entry_class'].objects.assert_called_once_with(
                upload_id=TEST_UPLOAD_ID
            )
            mock_data_layer['entry_objects'].delete.assert_called_once()
            mock_data_layer['upload_class'].get.assert_called_with(TEST_UPLOAD_ID)
            mock_data_layer['upload_instance'].delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_deletion_with_no_files(
        self, mock_data_layer, temporal_worker, temporal_test_queue
    ):
        """Test deletion when no files exist."""
        # Configure mocks - no files exist
        mock_data_layer['staging_files'].exists_for.return_value = False
        mock_data_layer['public_files'].exists_for.return_value = False

        async with temporal_worker() as env:
            input_data = TestFixtures.delete_upload_input()

            await env.client.execute_workflow(
                'DeleteUploadWorkflow',
                input_data,
                id='test-delete-upload-workflow-no-files',
                task_queue=temporal_test_queue,
            )

            # Verify file deletion was not called since files don't exist
            mock_data_layer['staging_files_instance'].delete.assert_not_called()
            mock_data_layer['public_files_instance'].delete.assert_not_called()


class TestProcessEntryWorkflow:
    """Tests for ProcessEntryWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_entry_processing(
        self, mock_data_layer, temporal_worker, temporal_test_queue
    ):
        """Test successful entry processing."""
        async with temporal_worker() as env:
            input_data = TestFixtures.process_entry_input()

            await env.client.execute_workflow(
                'ProcessEntryWorkflow',
                input_data,
                id='test-process-entry-workflow',
                task_queue=temporal_test_queue,
            )

            # Verify entry processing calls
            mock_data_layer['entry_class'].get.assert_called_with(TEST_ENTRY_ID)
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
    async def test_small_batch_direct_processing(
        self, mock_data_layer, temporal_worker, temporal_test_queue
    ):
        """Test processing small batch (<=1000 entries) directly."""
        entries = [TestFixtures.process_entry_input() for _ in range(5)]

        async with temporal_worker() as env:
            await env.client.execute_workflow(
                'BatchProcessEntriesWorkflow',
                entries,
                id='test-batch-process-small',
                task_queue=temporal_test_queue,
            )

        # Verify entries were processed
        assert (
            mock_data_layer['entry_class'].get.call_count == 10
        )  # 5 entries * 2 calls each (activity + success)


class TestProcessUploadWorkflow:
    """Tests for ProcessUploadWorkflow."""

    @pytest.mark.asyncio
    async def test_complete_upload_processing(
        self, mock_data_layer, monkeypatch, temporal_worker, temporal_test_queue
    ):
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

        async with temporal_worker() as env:
            input_data = TestFixtures.upload_processing_input()

            await env.client.execute_workflow(
                'ProcessUploadWorkflow',
                input_data,
                id='test-process-upload-workflow',
                task_queue=temporal_test_queue,
            )

        # Verify workflow ID management
        assert not mock_data_layer['upload_instance'].workflow_ids
        mock_data_layer['upload_instance'].save.assert_called()
        mock_data_layer['upload_instance'].update_files.assert_called_once()
        mock_data_layer['upload_instance'].match_all.assert_called_once()
        mock_data_layer['upload_instance'].cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_processing_loop_multiple_levels(
        self, mock_data_layer, monkeypatch, temporal_worker, temporal_test_queue
    ):
        """Test processing loop with multiple parser levels."""
        call_count = 0

        def mock_next_level_entries_multi_level(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count <= 2:
                return [Mock(entry_id=f'test-entry-{call_count}')]
            else:
                return []

        mock_data_layer[
            'upload_instance'
        ].next_level_entries.side_effect = mock_next_level_entries_multi_level
        monkeypatch.setattr('nomad.workflows.activities.parser_min_level', 0)

        async with temporal_worker() as env:
            input_data = TestFixtures.upload_processing_input()

            await env.client.execute_workflow(
                'ProcessUploadWorkflow',
                input_data,
                id='test-process-upload-workflow-levels',
                task_queue=temporal_test_queue,
            )

        # Verify next_level_entries was called multiple times
        assert mock_data_layer['upload_instance'].next_level_entries.call_count == 3


class TestProcessExampleUploadWorkflow:
    """Tests for ProcessExampleUploadWorkflow."""

    @pytest.mark.asyncio
    async def test_example_upload_processing(
        self, mock_data_layer, monkeypatch, temporal_worker, temporal_test_queue
    ):
        """Test example upload processing workflow."""
        # Mock to prevent the processing loop from running
        mock_data_layer['upload_instance'].next_level_entries.return_value = []
        monkeypatch.setattr('nomad.workflows.activities.parser_min_level', 0)

        async with temporal_worker() as env:
            input_data = TestFixtures.process_example_upload_input()
            await env.client.execute_workflow(
                'ProcessExampleUploadWorkflow',
                input_data,
                id='test-process-example-upload-workflow',
                task_queue=temporal_test_queue,
            )

            # Verify setup activity was called
            mock_data_layer[
                'upload_instance'
            ].setup_example_upload.assert_called_once_with(
                entry_point_id=TEST_EXAMPLE_UPLOAD_ID
            )


class TestEditUploadMetadataWorkflow:
    """Tests for EditUploadMetadataWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_metadata_edit(
        self, mock_data_layer, temporal_worker, temporal_test_queue
    ):
        """Test successful metadata editing."""
        async with temporal_worker() as env:
            input_data = TestFixtures.edit_upload_metadata_input()

            await env.client.execute_workflow(
                'EditUploadMetadataWorkflow',
                input_data,
                id='test-edit-upload-metadata-workflow',
                task_queue=temporal_test_queue,
            )

        # Verify metadata editing was called
        mock_data_layer[
            'upload_instance'
        ]._edit_upload_metadata_local.assert_called_once_with(
            {'title': 'Test Upload'}, TEST_USER_ID
        )

        # Verify that the process status is set to SUCCESS
        assert (
            mock_data_layer['upload_instance'].process_status == ProcessStatus.SUCCESS
        )
        mock_data_layer['upload_instance'].set_last_status_message.assert_called_with(
            'Process completed successfully'
        )


class TestImportBundleWorkflow:
    """Tests for ImportBundleWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_bundle_import(
        self, mock_data_layer, temporal_worker, temporal_test_queue
    ):
        """Test successful bundle import."""
        async with temporal_worker() as env:
            input_data = TestFixtures.import_bundle_input()

            await env.client.execute_workflow(
                'ImportBundleWorkflow',
                input_data,
                id='test-import-bundle-workflow',
                task_queue=temporal_test_queue,
            )

        # Verify bundle import was called
        mock_data_layer['upload_instance']._import_bundle_local.assert_called_once_with(
            TEST_BUNDLE_PATH, {}, None
        )

        # Verify that the process status is set to SUCCESS
        assert (
            mock_data_layer['upload_instance'].process_status == ProcessStatus.SUCCESS
        )
        mock_data_layer['upload_instance'].set_last_status_message.assert_called_with(
            'Process completed successfully'
        )


class TestPublishUploadWorkflow:
    """Tests for PublishUploadWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_upload_publish(
        self, mock_data_layer, temporal_worker, temporal_test_queue
    ):
        """Test successful upload publishing."""
        async with temporal_worker() as env:
            input_data = TestFixtures.publish_upload_input()

            await env.client.execute_workflow(
                'PublishUploadWorkflow',
                input_data,
                id='test-publish-upload-workflow',
                task_queue=temporal_test_queue,
            )

        # Verify publishing was called
        mock_data_layer[
            'upload_instance'
        ]._publish_upload_local.assert_called_once_with(None)

        # Verify that the process status is set to SUCCESS
        assert (
            mock_data_layer['upload_instance'].process_status == ProcessStatus.SUCCESS
        )
        mock_data_layer['upload_instance'].set_last_status_message.assert_called_with(
            'Process completed successfully'
        )


class TestPublishExternallyWorkflow:
    """Tests for PublishExternallyWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_external_publish(
        self, mock_data_layer, temporal_worker, temporal_test_queue
    ):
        """Test successful external publishing."""
        async with temporal_worker() as env:
            input_data = TestFixtures.publish_externally_input()

            await env.client.execute_workflow(
                'PublishExternallyWorkflow',
                input_data,
                id='test-publish-externally-workflow',
                task_queue=temporal_test_queue,
            )

            # Verify external publishing was called
        mock_data_layer[
            'upload_instance'
        ]._publish_externally_local.assert_called_once()

        # Verify that the process status is set to SUCCESS
        assert (
            mock_data_layer['upload_instance'].process_status == ProcessStatus.SUCCESS
        )
        mock_data_layer['upload_instance'].set_last_status_message.assert_called_with(
            'Process completed successfully'
        )


# Parameterized tests for common patterns
class TestWorkflowCommonPatterns:
    """Tests for common patterns across workflows."""

    @pytest.mark.parametrize(
        'workflow_class,input_data,activity_method',
        [
            (
                'EditUploadMetadataWorkflow',
                TestFixtures.edit_upload_metadata_input(),
                '_edit_upload_metadata_local',
            ),
            (
                'PublishUploadWorkflow',
                TestFixtures.publish_upload_input(),
                '_publish_upload_local',
            ),
            (
                'PublishExternallyWorkflow',
                TestFixtures.publish_externally_input(),
                '_publish_externally_local',
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_workflow_id_management_pattern(
        self,
        mock_data_layer,
        workflow_class,
        input_data,
        activity_method,
        temporal_worker,
        temporal_test_queue,
    ):
        """Test that workflows properly manage workflow IDs."""
        async with temporal_worker() as env:
            await env.client.execute_workflow(
                workflow_class,
                input_data,
                id=f'test-{workflow_class.lower()}-{uuid.uuid4()}',
                task_queue=temporal_test_queue,
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
    async def test_upload_workflow_id_assertion_error(
        self, mock_data_layer, temporal_worker, temporal_test_queue
    ):
        """Test that workflows fail when upload is already being processed."""
        # Set up upload to already have a workflow ID
        mock_data_layer['upload_instance'].workflow_ids = [EXISTING_WORKFLOW_ID]

        async with temporal_worker() as env:
            input_data = TestFixtures.edit_upload_metadata_input()
            with pytest.raises(
                Exception
            ):  # Should raise AssertionError from add_workflow_id_activity
                await env.client.execute_workflow(
                    'EditUploadMetadataWorkflow',
                    input_data,
                    id='test-workflow-id-conflict',
                    task_queue=temporal_test_queue,
                )

    @pytest.mark.parametrize(
        'workflow_class, input_fixture, activity_to_fail, mock_target_name, expected_status_message',
        [
            (
                'ProcessEntryWorkflow',
                TestFixtures.process_entry_input,
                '_process_entry_local',
                'entry_instance',
                'Process process_entry failed',
            ),
            (
                'ProcessUploadWorkflow',
                TestFixtures.upload_processing_input,
                'update_files',
                'upload_instance',
                'Process upload failed',
            ),
            (
                'EditUploadMetadataWorkflow',
                TestFixtures.edit_upload_metadata_input,
                '_edit_upload_metadata_local',
                'upload_instance',
                'Edit metadata failed',
            ),
            (
                'ImportBundleWorkflow',
                TestFixtures.import_bundle_input,
                '_import_bundle_local',
                'upload_instance',
                'Import bundle failed',
            ),
            (
                'PublishUploadWorkflow',
                TestFixtures.publish_upload_input,
                '_publish_upload_local',
                'upload_instance',
                'Publish upload failed',
            ),
            (
                'PublishExternallyWorkflow',
                TestFixtures.publish_externally_input,
                '_publish_externally_local',
                'upload_instance',
                'Publish externally failed',
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_workflow_failure_handling(
        self,
        mock_data_layer,
        monkeypatch,
        workflow_class,
        input_fixture,
        activity_to_fail,
        mock_target_name,
        expected_status_message,
        temporal_worker,
        temporal_test_queue,
    ):
        """Test that workflows handle failures consistently with a try-catch-finally pattern."""
        # Mock the activity to fail
        mock_target = mock_data_layer[mock_target_name]
        getattr(mock_target, activity_to_fail).side_effect = Exception(
            f'Simulated {activity_to_fail} failure'
        )

        # Special setup for ProcessUploadWorkflow
        if workflow_class == 'ProcessUploadWorkflow':
            monkeypatch.setattr('nomad.workflows.activities.parser_min_level', 0)

        async with temporal_worker() as env:
            input_data = input_fixture()
            with pytest.raises(Exception):
                await env.client.execute_workflow(
                    workflow_class,
                    input_data,
                    id=f'test-{workflow_class.lower()}-{uuid.uuid4()}-failure-pattern',
                    task_queue=temporal_test_queue,
                )

        # Verify consistent failure handling
        assert mock_target.process_status == ProcessStatus.FAILURE
        mock_target.last_status_message = expected_status_message
        mock_target.save.assert_called()

        # Verify workflow ID is cleared for upload-level workflows
        if mock_target_name == 'upload_instance':
            assert not mock_target.workflow_ids
            # Verify workflow ID was added and then removed
            assert mock_target.save.call_count >= 2

    @pytest.mark.asyncio
    async def test_workflow_id_cleanup_on_success(
        self, mock_data_layer, temporal_worker, temporal_test_queue
    ):
        """Test that workflow IDs are properly cleaned up on successful execution."""
        async with temporal_worker() as env:
            input_data = TestFixtures.edit_upload_metadata_input()

            await env.client.execute_workflow(
                'EditUploadMetadataWorkflow',
                input_data,
                id='test-workflow-id-cleanup-success',
                task_queue=temporal_test_queue,
            )

        # Verify workflow ID was added and then removed (cleanup)
        assert mock_data_layer['upload_instance'].save.call_count >= 2
        assert not mock_data_layer['upload_instance'].workflow_ids

    @pytest.mark.asyncio
    async def test_partial_entry_failure_upload_success(
        self, mock_data_layer, monkeypatch, temporal_worker, temporal_test_queue
    ):
        """Test that when individual entries fail, the upload itself is not marked as a failure."""

        # Mock next_level_entries to return multiple entries
        def mock_next_level_entries_side_effect(*args, **kwargs):
            if not hasattr(mock_next_level_entries_side_effect, 'call_count'):
                mock_next_level_entries_side_effect.call_count = 0

            mock_next_level_entries_side_effect.call_count += 1

            if mock_next_level_entries_side_effect.call_count == 1:
                # Return two entries - one will succeed, one will fail
                return [Mock(entry_id='test-entry-1'), Mock(entry_id='test-entry-2')]
            else:
                return []

        mock_data_layer[
            'upload_instance'
        ].next_level_entries.side_effect = mock_next_level_entries_side_effect

        # Mock process_entry_activity to fail for one specific entry
        def mock_process_entry_side_effect(input_data):
            if input_data.entry_id == 'test-entry-2':
                raise Exception('Simulated entry processing failure')
            return 'success'

        mock_data_layer[
            'entry_instance'
        ]._process_entry_local.side_effect = mock_process_entry_side_effect

        # Mock parser_min_level
        monkeypatch.setattr('nomad.workflows.activities.parser_min_level', 0)

        async with temporal_worker() as env:
            input_data = TestFixtures.upload_processing_input()

            await env.client.execute_workflow(
                'ProcessUploadWorkflow',
                input_data,
                id='test-partial-entry-failure',
                task_queue=temporal_test_queue,
            )

        # Verify that the upload is still marked as successful despite entry failures
        mock_data_layer['upload_instance'].process_status = ProcessStatus.SUCCESS
        mock_data_layer['upload_instance'].set_last_status_message.assert_called_with(
            'Process completed successfully'
        )

        # Verify that entry processing was attempted for both entries
        # 24 calls accounts for the number of retries
        assert mock_data_layer['entry_class'].get.call_count == 24

        # Verify that the upload workflow completed successfully
        # (The upload should not be marked as failed due to individual entry failures)
        assert (
            mock_data_layer['upload_instance'].save.call_count >= 2
        )  # Add + remove workflow ID calls
