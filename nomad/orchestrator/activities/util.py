from collections.abc import Callable

from nomad.orchestrator.shared.constant import TaskQueue
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


def get_nomad_internal_activities() -> list[Callable]:
    return [
        delete_upload_search_activity,
        delete_upload_files_activity,
        delete_upload_entries_activity,
        delete_upload_record_activity,
        process_entry_activity,
        process_entry_success,
        process_entry_failure_activity,
        process_upload_failure_activity,
        process_upload_success,
        cleanup_activity,
        next_level_entries,
        match_all_activity,
        update_files_activity,
        setup_example_upload_activity,
        add_workflow_id_activity,
        remove_workflow_id_activity,
        edit_upload_metadata_activity,
        import_bundle_activity,
        publish_upload_activity,
        publish_externally_activity,
    ]


def get_all_activities(task_queue: TaskQueue) -> list[Callable]:
    activities = []

    if task_queue == TaskQueue.NOMAD_INTERNAL_WORKFLOWS:
        activities.extend(get_nomad_internal_activities())
    return activities
