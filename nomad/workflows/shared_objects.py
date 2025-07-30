#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD. See https://nomad-lab.eu for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CreateEntryInput:
    upload_id: str
    entry_id: str
    mainfile: str
    parser_name: str
    mainfile_key: str | None = None


@dataclass
class MatchedFile:
    parser_name: str
    parser_level: int
    mainfile: str
    mainfile_key: str | None = None


@dataclass
class PerformFileOpsInput:
    upload_id: str
    file_operations: list[dict[str, Any]]
    is_public_upload: bool


@dataclass
class PerformFileOpsOutput:
    updated_files: set[str]


@dataclass
class ProcessEntryActivityInput:
    upload_id: str
    entry_id: str
    workflow_id: str


@dataclass
class ArchiveEntryData:
    processing_logs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class UploadWorkflowIdInput:
    upload_id: str
    workflow_id: str
    failure_message: str | None = None


@dataclass
class NextLevelEntryResult:
    next_parser_level: int | None
    entries_to_be_processed: list[ProcessEntryActivityInput]


@dataclass
class UploadProcessingWorkflowInput:
    upload_id: str
    workflow_id: str
    file_operations: list[dict[str, Any]] | None = None
    reprocess_settings: dict[str, Any] | None = None
    path_filter: str | None = None
    only_updated_files: bool = False
    publish_directly_after_processing: bool = False
    updated_files: set[str] | None = None
    min_level: int = 0
    batch_id: int = 0


@dataclass
class PublishUploadWorkflowInput:
    upload_id: str
    embargo_length: int | None = None


@dataclass
class DeleteUploadWorkflowInput:
    upload_id: str


@dataclass
class EditUploadMetadataWorkflowInput:
    upload_id: str
    user_id: str
    edit_request_json: dict[str, Any]
    upload_id_for_direct_edit: str | None = None


@dataclass
class ImportBundleWorkflowInput:
    upload_id: str
    bundle_path: str
    import_settings: dict[str, Any]
    embargo_length: int | None = None


@dataclass
class ProcessExampleUploadWorkflowInput:
    upload_id: str
    example_upload_id: str
    file_operations: list[dict[str, Any]] | None = None
    publish_directly: bool = False


@dataclass
class PublishExternallyWorkflowInput:
    upload_id: str
    embargo_length: int | None = None
