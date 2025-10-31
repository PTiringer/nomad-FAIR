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


import pytest

from nomad.config import config
from nomad.config.models.config import BundleImportSettings
from nomad.processing import Upload
from tests.processing.test_data import assert_processing


@pytest.mark.parametrize(
    'import_settings, embargo_length',
    [
        # pytest.param(
        #     config.BundleImportSettings(include_archive_files=True, trigger_processing=False), 0,
        #     id='no-processing'),
        pytest.param(
            BundleImportSettings(include_archive_files=False, trigger_processing=True),
            17,
            id='trigger-processing',
        )
    ],
)
def test_publish_to_central_nomad(
    proc_infra,
    monkeypatch,
    oasis_publishable_upload,
    user1,
    no_warn,
    import_settings,
    embargo_length,
):
    upload_id, suffix = oasis_publishable_upload
    old_upload = Upload.get(upload_id)

    import_settings = config.bundle_import.default_settings.customize(import_settings)
    monkeypatch.setattr('nomad.config.bundle_import.default_settings', import_settings)
    monkeypatch.setattr('nomad.config.bundle_import.allow_bundles_from_oasis', True)

    old_upload.publish_externally(embargo_length=embargo_length)
    old_upload.block_until_complete()
    assert_processing(old_upload, old_upload.published, '_publish_externally')
    old_upload = Upload.get(upload_id)
    new_upload = Upload.get(upload_id + suffix)
    new_upload.block_until_complete()
    assert_processing(new_upload, old_upload.published, '_import_bundle')
    assert len(old_upload.successful_entries) == len(new_upload.successful_entries) == 1
    if embargo_length is None:
        embargo_length = old_upload.embargo_length
    old_entry = old_upload.successful_entries[0]
    new_entry = new_upload.successful_entries[0]
    old_entry_metadata_dict = old_entry.full_entry_metadata(old_upload).m_to_dict()
    new_entry_metadata_dict = new_entry.full_entry_metadata(new_upload).m_to_dict()
    for k, v in old_entry_metadata_dict.items():
        if k == 'with_embargo':
            assert new_entry_metadata_dict[k] == (embargo_length > 0)
        elif k not in (
            'upload_id',
            'entry_id',
            'upload_create_time',
            'entry_create_time',
            'last_processing_time',
            'publish_time',
            'embargo_length',
            'n_quantities',
            'quantities',
        ):  # TODO: n_quantities and quantities update problem?
            assert new_entry_metadata_dict[k] == v, f'Metadata not matching: {k}'
    assert new_entry.datasets == ['dataset_id']
    assert old_upload.published_to[0] == config.oasis.central_nomad_deployment_url
    assert new_upload.from_oasis and new_upload.oasis_deployment_url
    assert new_upload.embargo_length == embargo_length
    assert (
        old_upload.upload_files.access == 'restricted'
        if old_upload.with_embargo
        else 'public'
    )
    assert (
        new_upload.upload_files.access == 'restricted'
        if new_upload.with_embargo
        else 'public'
    )
