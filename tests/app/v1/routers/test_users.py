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

from tests.fixtures.users import users
from tests.utils import fake_user_uuid


def assert_user(user, expected_user):
    assert user['first_name'] == expected_user['first_name']
    assert user['last_name'] == expected_user['last_name']
    assert 'email' not in user


def test_me(auth_headers, client, app_token_auth):
    response = client.get('users/me', headers=auth_headers['user1'])
    assert response.status_code == 200

    response = client.get('users/me', headers=app_token_auth)
    assert response.status_code == 200


def test_me_auth_required(client):
    response = client.get('users/me')
    assert response.status_code == 401


def test_me_auth_bad_token(client):
    response = client.get('users/me', headers={'Authentication': 'Bearer NOTATOKEN'})
    assert response.status_code == 401


def test_user_landing_page_roundtrip(auth_headers, client, tmp_path, monkeypatch):
    monkeypatch.setattr(config.fs, 'north_home', str(tmp_path))
    landing_page = 'widgets:\n  - type: hero\n    title: Hello\n'

    response = client.get('users/me/landing-page', headers=auth_headers['user1'])
    assert response.status_code == 404

    response = client.put(
        'users/me/landing-page',
        headers={
            **auth_headers['user1'],
            'Content-Type': 'application/yaml',
        },
        content=landing_page,
    )
    assert response.status_code == 200
    assert response.text == landing_page

    stored_path = (
        tmp_path
        / fake_user_uuid(1)
        / 'landing-pages'
        / 'user-home.yaml'
    )
    assert stored_path.read_text() == landing_page

    response = client.get('users/me/landing-page', headers=auth_headers['user1'])
    assert response.status_code == 200
    assert response.text == landing_page


def test_user_landing_page_rejects_invalid_yaml(auth_headers, client, tmp_path, monkeypatch):
    monkeypatch.setattr(config.fs, 'north_home', str(tmp_path))

    response = client.put(
        'users/me/landing-page',
        headers={
            **auth_headers['user1'],
            'Content-Type': 'application/yaml',
        },
        content='widgets: [\n',
    )
    assert response.status_code == 400


def test_user_sidebar_roundtrip(auth_headers, client, tmp_path, monkeypatch):
    monkeypatch.setattr(config.fs, 'north_home', str(tmp_path))
    sidebar = 'title: My pages\nwiki_pages:\n  enabled: true\n  limit: 10\n'

    response = client.get('users/me/sidebar', headers=auth_headers['user1'])
    assert response.status_code == 404

    response = client.put(
        'users/me/sidebar',
        headers={**auth_headers['user1'], 'Content-Type': 'application/yaml'},
        content=sidebar,
    )
    assert response.status_code == 200
    assert response.text == sidebar

    stored_path = (
        tmp_path / fake_user_uuid(1) / 'landing-pages' / 'user-sidebar.yaml'
    )
    assert stored_path.read_text() == sidebar

    response = client.get('users/me/sidebar', headers=auth_headers['user1'])
    assert response.status_code == 200
    assert response.text == sidebar


def test_invite(auth_headers, client, no_warn):
    rv = client.put(
        'users/invite',
        headers=auth_headers['user1'],
        json={
            'first_name': 'John',
            'last_name': 'Doe',
            'affiliation': 'Affiliation',
            'email': 'john.doe@affiliation.edu',
        },
    )
    assert rv.status_code == 200
    data = rv.json()
    keys = data.keys()
    required_keys = ['name', 'email', 'user_id']
    assert all(key in keys for key in required_keys)


@pytest.mark.parametrize(
    'args, expected_status_code, expected_content',
    [
        pytest.param(
            dict(prefix='Sheldon'),
            200,
            users[fake_user_uuid(1)],
            id='search-user',
        ),
        pytest.param(
            dict(user_id=fake_user_uuid(1)),
            200,
            users[fake_user_uuid(1)],
            id='one-user-id',
        ),
        pytest.param(
            dict(user_id=[fake_user_uuid(1), fake_user_uuid(2)]),
            200,
            [
                users[fake_user_uuid(1)],
                users[fake_user_uuid(2)],
            ],
            id='multi-user-id',
        ),
        pytest.param(
            dict(user_id=[fake_user_uuid(1), fake_user_uuid(9)]),
            200,
            [users[fake_user_uuid(1)]],
            id='wrong-user-id',
        ),
    ],
)
def test_users(client, args, expected_status_code, expected_content):
    prefix = args.get('prefix', None)
    user_id = args.get('user_id', None)

    if prefix:
        rv = client.get(f'users?prefix={prefix}')
        assert rv.status_code == expected_status_code
        data = rv.json()
        assert len(data['data']) == 1
        user = data['data'][0]
        for key in ['name', 'user_id']:
            assert key in user
        for value in user.values():
            assert value is not None
        assert_user(user, expected_content)

    if user_id:
        if not isinstance(user_id, list):
            rv = client.get(f'users?user_id={user_id}')
            assert rv.status_code == expected_status_code
            if rv.status_code == 200:
                data = rv.json()
                user = data['data'][0]
                assert_user(user, expected_content)
        else:
            rv = client.get(f'users?user_id={"&user_id=".join(user_id)}')
            assert rv.status_code == expected_status_code
            if rv.status_code == 200:
                data = rv.json()
                users = data['data']
                for user, expected_user in zip(users, expected_content):
                    assert_user(user, expected_user)


@pytest.mark.parametrize(
    'args, expected_status_code, expected_content',
    [
        pytest.param(
            dict(user_id=fake_user_uuid(1)),
            200,
            users[fake_user_uuid(1)],
            id='valid-user',
        )
    ],
)
def test_users_id(client, args, expected_status_code, expected_content):
    user_id = args['user_id']
    rv = client.get(f'users/{user_id}')
    assert rv.status_code == expected_status_code
    if rv.status_code == 200:
        user = rv.json()
        assert_user(user, expected_content)
