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

import asyncio
import io
import os
import time
import zipfile

import pytest

from nomad.bundles import BundleExporter
from nomad.config import config
from nomad.config.models.config import BundleImportSettings
from nomad.processing import ProcessStatus, Upload
from tests.app.v1.routers.common import assert_response, perform_get
from tests.app.v1.routers.uploads.test_basic_uploads import (
    assert_file_upload_and_processing,
    assert_gets_published,
    assert_metadata_edited,
    assert_processing,
    perform_post_put_file,
    perform_post_upload_action,
    set_upload_entry_metadata,
)
from tests.processing import test_data as test_processing
from tests.test_files import example_file_mainfile_different_atoms
from tests.utils import build_url

from .common import assert_upload


@pytest.mark.parametrize(
    'mode, user, expected_status_code',
    [pytest.param('multipart', 'user1', 409, id='conflict_in_concurrent_editing')],
)
def test_editing_raw_file(
    auth_headers,
    upload_tokens,
    client,
    non_empty_processed,
    example_data_writeable,
    proc_infra,
    mode,
    user,
    expected_status_code,
):
    upload_id = non_empty_processed.upload_id
    target_path = 'examples_template'
    action = 'PUT'
    path = 'examples_template/template.json'
    archive_url = f'uploads/{upload_id}/archive/mainfile/{path}'
    target_url = f'uploads/{upload_id}/raw/{target_path}'
    user_auth = auth_headers[user]

    # Get an existing upload with entries
    response = perform_get(client, archive_url, user_auth=user_auth)
    assert response.status_code == 200
    response_json = response.json()
    entry_hash = response_json['data']['archive']['metadata']['entry_hash']

    # First edit
    query_args = {
        'file_name': 'example.json',
        'wait_for_processing': True,
        'include_archive': True,
        'entry_hash': entry_hash,
    }
    response, _ = assert_file_upload_and_processing(
        auth_headers,
        upload_tokens,
        client,
        action,
        target_url,
        mode,
        user,
        upload_id,
        example_file_mainfile_different_atoms,
        target_path,
        query_args,
        True,
        False,
        200,
        ProcessStatus.SUCCESS,
        ['examples_template/template.json'],
        False,
        True,
    )

    # Second edit on the same entry
    query_args = {
        'file_name': 'example.json',
        'wait_for_processing': True,
        'entry_hash': entry_hash,
    }
    response, _ = assert_file_upload_and_processing(
        auth_headers,
        upload_tokens,
        client,
        action,
        target_url,
        mode,
        user,
        upload_id,
        example_file_mainfile_different_atoms,
        target_path,
        query_args,
        True,
        False,
        expected_status_code,
        None,
        None,
        None,
        None,
    )

    # Get the updated archive
    response = perform_get(
        client, f'uploads/{upload_id}/archive/mainfile/{path}', user_auth=user_auth
    )
    assert response.status_code == 200
    response_json = response.json()
    entry_hash = response_json['data']['archive']['metadata']['entry_hash']

    # Edit with the updated hash code
    query_args = {
        'file_name': 'example.json',
        'wait_for_processing': True,
        'include_archive': True,
        'entry_hash': entry_hash,
    }
    response, _ = assert_file_upload_and_processing(
        auth_headers,
        upload_tokens,
        client,
        action,
        target_url,
        mode,
        user,
        upload_id,
        example_file_mainfile_different_atoms,
        target_path,
        query_args,
        True,
        False,
        200,
        ProcessStatus.SUCCESS,
        ['examples_template/template.json'],
        False,
        True,
    )

    # Get the updated archive
    response = perform_get(
        client, f'uploads/{upload_id}/archive/mainfile/{path}', user_auth=user_auth
    )
    assert response.status_code == 200
    response_json = response.json()
    entry_hash = response_json['data']['archive']['metadata']['entry_hash']

    # Somebody deletes the file faster
    response = client.delete(f'uploads/{upload_id}/raw/{path}', headers=user_auth)
    assert response.status_code == 200
    time.sleep(1)

    # Editing the file which was deleted by someone else
    query_args = {
        'file_name': 'example.json',
        'wait_for_processing': True,
        'entry_hash': entry_hash,
    }
    response, _ = assert_file_upload_and_processing(
        auth_headers,
        upload_tokens,
        client,
        action,
        target_url,
        mode,
        user,
        upload_id,
        example_file_mainfile_different_atoms,
        target_path,
        query_args,
        True,
        False,
        expected_status_code,
        None,
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    'import_settings, query_args',
    [
        pytest.param(
            BundleImportSettings(include_archive_files=False, trigger_processing=True),
            dict(embargo_length=0),
            id='trigger-processing',
        ),
        pytest.param(
            BundleImportSettings(include_archive_files=True, trigger_processing=False),
            dict(embargo_length=28),
            id='no-processing',
        ),
    ],
)
def test_post_upload_action_publish_to_central_nomad(
    auth_headers,
    client,
    proc_infra,
    monkeypatch,
    oasis_publishable_upload,
    users_dict,
    import_settings,
    query_args,
):
    """Tests the publish action with to_central_nomad=True."""
    upload_id, suffix = oasis_publishable_upload
    query_args['to_central_nomad'] = True
    embargo_length = query_args.get('embargo_length')
    expected_status_code = 200
    user = 'user0'
    user_auth = auth_headers[user]
    old_upload = Upload.get(upload_id)

    import_settings = config.bundle_import.default_settings.customize(import_settings)
    monkeypatch.setattr('nomad.config.bundle_import.default_settings', import_settings)
    monkeypatch.setattr('nomad.config.bundle_import.allow_bundles_from_oasis', True)

    # Finally, invoke the method to publish to central nomad
    response = perform_post_upload_action(
        client, user_auth, upload_id, 'publish', **query_args
    )

    assert_response(response, expected_status_code)
    if expected_status_code == 200:
        upload = assert_upload(response.json())
        assert upload['current_process'] == '_publish_externally'
        assert upload['process_running']
        assert_processing(client, upload_id, user_auth, published=old_upload.published)
        assert_processing(
            client, upload_id + suffix, user_auth, published=old_upload.published
        )

        old_upload = Upload.get(upload_id)
        new_upload = Upload.get(upload_id + suffix)
        assert (
            len(old_upload.successful_entries)
            == len(new_upload.successful_entries)
            == 1
        )
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


@pytest.mark.parametrize(
    'kwargs',
    [
        pytest.param(dict(expected_status_code=200), id='no-args'),
        pytest.param(
            dict(query_args={'embargo_length': 12}, expected_status_code=200),
            id='non-standard-embargo',
        ),
        pytest.param(
            dict(query_args={'embargo_length': 24}, expected_status_code=200),
            id='non-standard-embargo-length-only',
        ),
        pytest.param(
            dict(query_args={'embargo_length': 100}, expected_status_code=400),
            id='illegal-embargo-length',
        ),
        pytest.param(
            dict(query_args={'embargo_length': 0}, expected_status_code=200),
            id='no-embargo',
        ),
        pytest.param(
            dict(upload_id='id_empty_w', expected_status_code=400), id='empty'
        ),
        pytest.param(
            dict(upload_id='id_processing_w', expected_status_code=400), id='processing'
        ),
        pytest.param(
            dict(upload_id='id_published_w', expected_status_code=400),
            id='already-published',
        ),
        pytest.param(dict(user=None, expected_status_code=401), id='no-credentials'),
        pytest.param(
            dict(user='invalid', expected_status_code=401), id='invalid-credentials'
        ),
        pytest.param(dict(user='user2', expected_status_code=401), id='no-access'),
    ],
)
@pytest.mark.asyncio
async def test_post_upload_action_publish(
    auth_headers, client, temporal_worker, example_data_writeable, kwargs
):
    """Tests the publish action with various arguments."""
    upload_id = kwargs.get('upload_id', 'id_unpublished_w')
    query_args = kwargs.get('query_args', {})
    expected_status_code = kwargs.get('expected_status_code', 200)
    user = kwargs.get('user', 'user1')
    user_auth = auth_headers[user]

    async with temporal_worker():
        response = await asyncio.to_thread(
            lambda: perform_post_upload_action(
                client, user_auth, upload_id, 'publish', **query_args
            )
        )

    assert_response(response, expected_status_code)
    if expected_status_code == 200:
        upload = assert_upload(response.json())
        assert upload['process_running']

        assert_gets_published(
            client, upload_id, user_auth, current_embargo_length=12, **query_args
        )


@pytest.mark.parametrize(
    'upload_id, user, preprocess, expected_status_code',
    [
        pytest.param('id_published_w', 'user1', None, 200, id='ok'),
        pytest.param('id_published_w', 'user2', None, 401, id='no-access'),
        pytest.param('id_published_w', 'user2', 'make-coauthor', 200, id='ok-coauthor'),
        pytest.param('id_published_w', None, None, 401, id='no-credentials'),
        pytest.param('id_published_w', 'invalid', None, 401, id='invalid-credentials'),
        pytest.param('id_unpublished_w', 'user1', None, 400, id='not-published'),
        pytest.param('id_published_w', 'user1', 'lift', 400, id='already-lifted'),
    ],
)
@pytest.mark.asyncio
async def test_post_upload_action_lift_embargo(
    auth_headers,
    client,
    proc_infra,
    example_data_writeable,
    users_dict,
    upload_id,
    user,
    preprocess,
    expected_status_code,
    temporal_worker,
):
    user_auth = auth_headers[user]
    user = users_dict.get(user)

    async with temporal_worker():
        if preprocess:
            if preprocess == 'lift':
                metadata = {'embargo_length': 0}
            elif preprocess == 'make-coauthor':
                metadata = {'coauthors': user.user_id}
            upload = Upload.get(upload_id)
            await upload._start_edit_upload_metadata_workflow(
                dict(metadata=metadata), config.services.admin_user_id
            )

        response = await asyncio.to_thread(
            lambda: perform_post_upload_action(
                client, user_auth, upload_id, 'lift-embargo'
            )
        )
    assert_response(response, expected_status_code)
    if expected_status_code == 200:
        assert_metadata_edited(user, {'embargo_length': 0}, [upload_id])


@pytest.mark.parametrize(
    'upload_id, user, query_args, expected_status_code',
    [
        pytest.param('id_published_w', 'user1', dict(), 200, id='published-owner'),
        pytest.param('id_published_w', 'user0', dict(), 200, id='published-admin'),
        pytest.param('id_published_w', 'user2', dict(), 401, id='published-not-owner'),
        pytest.param(
            'id_published_w',
            'user1',
            dict(include_raw_files=False),
            200,
            id='published-owner-exclude-raw',
        ),
        pytest.param(
            'id_published_w',
            'user1',
            dict(include_archive_files=False),
            200,
            id='published-owner-exclude-archive',
        ),
        pytest.param('id_unpublished_w', 'user1', dict(), 200, id='unpublished-owner'),
        pytest.param('id_unpublished_w', 'user0', dict(), 200, id='unpublished-admin'),
        pytest.param(
            'id_unpublished_w',
            'user2',
            dict(),
            401,
            id='unpublished-not-owner',
        ),
    ],
)
def test_get_upload_bundle(
    auth_headers,
    client,
    proc_infra,
    example_data_writeable,
    upload_id,
    user,
    query_args,
    expected_status_code,
):
    include_raw_files = query_args.get('include_raw_files', True)
    include_archive_files = query_args.get('include_archive_files', True)

    url = build_url(f'uploads/{upload_id}/bundle', query_args)
    response = perform_get(client, url, user_auth=auth_headers[user])
    assert_response(response, expected_status_code)
    if expected_status_code == 200:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            upload = Upload.get(upload_id)
            upload_files = upload.upload_files
            expected_files = set(['bundle_info.json'])
            for dirpath, __, filenames in os.walk(upload_files.os_path):
                for filename in filenames:
                    os_path = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(os_path, upload_files.os_path)
                    include = False
                    include |= (
                        rel_path.startswith('raw')
                        and not rel_path.endswith('.h5')
                        and include_raw_files
                    )
                    include |= rel_path.startswith('archive') and include_archive_files
                    if include:
                        expected_files.add(rel_path)
            assert expected_files == set(zip_file.namelist())


@pytest.mark.parametrize(
    'publish, test_duplicate, user, export_args, query_args, expected_status_code',
    [
        pytest.param(True, False, 'user0', dict(), dict(), 200, id='published-admin'),
        pytest.param(
            False, False, 'user0', dict(), dict(), 200, id='unpublished-admin'
        ),
        pytest.param(True, True, 'user0', dict(), dict(), 400, id='duplicate'),
        pytest.param(True, False, 'user2', dict(), dict(), 200, id='not-oasis-admin'),
        pytest.param(True, False, None, dict(), dict(), 401, id='no-credentials'),
    ],
)
def test_post_upload_bundle(
    auth_headers,
    client,
    proc_infra,
    non_empty_uploaded,
    internal_example_user_metadata,
    publish,
    test_duplicate,
    user,
    users_dict,
    export_args,
    query_args,
    expected_status_code,
):
    non_empty_processed = test_processing.run_processing(
        non_empty_uploaded, users_dict[user or 'user0']
    )
    # Create the bundle
    set_upload_entry_metadata(non_empty_processed, internal_example_user_metadata)
    if publish:
        non_empty_processed.publish_upload()
        non_empty_processed.block_until_complete(interval=0.01)
    upload = non_empty_processed
    upload_id = upload.upload_id
    export_path = os.path.join(config.fs.tmp, 'bundle_' + upload_id)
    export_args_with_defaults = dict(
        export_as_stream=False,
        export_path=export_path,
        zipped=True,
        overwrite=True,
        export_settings=config.bundle_export.default_settings,
    )
    export_args_with_defaults.update(export_args)
    BundleExporter(upload, **export_args_with_defaults).export_bundle()

    if not test_duplicate:
        # Delete the upload so we can import the bundle without id collisions
        upload.delete_upload_local()
    # Finally, import the bundle
    user_auth = auth_headers[user]
    response = perform_post_put_file(
        client, 'POST', 'uploads/bundle', 'stream', export_path, user_auth, **query_args
    )
    assert_response(response, expected_status_code)
    if expected_status_code == 200:
        assert_processing(client, upload_id, user_auth, published=publish)
        upload = Upload.get(upload_id)
        assert upload.from_oasis and upload.oasis_deployment_url


def test_stop_processing_action_temporal_disabled(
    non_empty_uploaded,
    user1,
    auth_headers,
    client,
    proc_infra,
):
    """Tests the endpoint for stopping the processing of an upload."""
    upload_id, _ = non_empty_uploaded

    upload_owner = user1
    upload = Upload.create(
        upload_id=upload_id,
        main_author=upload_owner,
        workflow_ids=['example-workflow-id'],
    )
    upload.save()
    upload.process_status = ProcessStatus.PENDING
    upload.save()

    user_auth = auth_headers['user1']

    # Perform the request
    response = perform_post_upload_action(
        client, user_auth, upload_id, 'stop-processing'
    )

    assert_response(response, 400)
