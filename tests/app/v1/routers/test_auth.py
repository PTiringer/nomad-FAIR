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
from fastapi import HTTPException, Request

from nomad.app.v1.models.models import User
from nomad.app.v1.routers.auth import get_current_user
from nomad.config.models.config import ModeEnum

# Tests for OIDC authentication endpoints


@pytest.mark.parametrize(
    'form_data, expected_status',
    [
        pytest.param(
            dict(username='user1', password='password', grant_type='password'),
            200,
            id='valid_credentials',
        ),
        pytest.param(
            dict(username='bad', password='credentials', grant_type='password'),
            401,
            id='invalid_credentials',
        ),
        pytest.param(
            dict(username='user1', password='password'),
            422,
            id='missing_grant_type',
        ),
    ],
)
def test_post_token_various_cases(client, user1, form_data, expected_status):
    if form_data.get('username') == 'user1':
        form_data['username'] = user1.username

    response = client.post('auth/token', data=form_data)
    assert response.status_code == expected_status

    if expected_status == 200:
        assert response.headers.get('Cache-Control') == 'no-store'
        assert response.headers.get('Pragma') == 'no-cache'


# Tests for NOMAD custom tokens (simple token, upload token)


def test_get_signature_token(auth_headers, client):
    response = client.get('auth/signature_token', headers=auth_headers['user1'])
    assert response.status_code == 200
    assert response.json().get('signature_token') is not None


def test_get_signature_token_unauthorized(auth_headers, client):
    response = client.get('auth/signature_token', headers=None)
    assert response.status_code == 401
    response = client.get('auth/signature_token', headers=auth_headers['invalid'])
    assert response.status_code == 401


@pytest.mark.parametrize(
    'expires_in, status_code',
    [
        (0, 422),
        (30 * 60, 200),
        (2 * 60 * 60, 200),
        (31 * 24 * 60 * 60, 422),
        (None, 422),
    ],
)
def test_get_app_token(auth_headers, client, expires_in, status_code):
    response = client.get(
        'auth/app_token',
        headers=auth_headers['user1'],
        params={'expires_in': expires_in},
    )
    assert response.status_code == status_code
    if status_code == 200:
        assert response.json().get('app_token') is not None


def test_get_app_token_unauthorized(auth_headers, client):
    response = client.get('auth/app_token', headers=None, params={'expires_in': 60})
    assert response.status_code == 401
    headers = auth_headers['invalid']
    response = client.get('auth/app_token', headers=headers, params={'expires_in': 60})
    assert response.status_code == 401


# Tests for `get_current_user`


@pytest.fixture
def allowed_user():
    return User(user_id='123', email='test@example.com', username='tester')


@pytest.mark.parametrize('allow_keycloak_token', [True, False])
@pytest.mark.parametrize('allow_simple_token', [True, False])
@pytest.mark.parametrize('allow_upload_token', [True, False])
@pytest.mark.parametrize('get_user_from_keycloak_token', [True, False])
@pytest.mark.parametrize('get_user_from_simple_token', [True, False])
@pytest.mark.parametrize('get_user_from_upload_token', [True, False])
def test_get_current_user_auth_methods(
    allow_keycloak_token: bool,
    allow_simple_token: bool,
    allow_upload_token: bool,
    get_user_from_keycloak_token: bool,
    get_user_from_simple_token: bool,
    get_user_from_upload_token: bool,
    allowed_user,
    monkeypatch,
):
    if allow_simple_token:  # ensure dummy simple token could decode as JWT
        monkeypatch.setattr(
            'nomad.app.v1.routers.auth.jwt.decode',
            lambda *args, **kwargs: {'user': allowed_user.user_id, 'exp': 600},
        )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_keycloak_token',
        lambda *args, **kwargs: allowed_user if get_user_from_keycloak_token else None,
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_simple_token',
        lambda *args, **kwargs: allowed_user if get_user_from_simple_token else None,
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_upload_token',
        lambda *_: allowed_user if get_user_from_upload_token else None,
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.datamodel.User.get',
        lambda *args, **kwargs: allowed_user,
    )

    dep = get_current_user(
        required=True,
        allow_keycloak_token=allow_keycloak_token,
        allow_simple_token=allow_simple_token,
        allow_upload_token=allow_upload_token,
    )

    if any(
        [
            allow_keycloak_token and get_user_from_keycloak_token,
            allow_simple_token and get_user_from_simple_token,
            allow_upload_token and get_user_from_upload_token,
        ]
    ):
        assert (
            dep(
                keycloak_token='abc' if allow_keycloak_token else None,
                simple_token='def' if allow_simple_token else None,
                upload_token='ghi' if allow_upload_token else None,
            )
            == allowed_user
        )
    else:
        with pytest.raises(HTTPException, match='Authentication required.') as exc:
            dep()
        assert exc.value.status_code == 401


def test_get_current_user_rejects_query_token():
    """Ensure that passing upload token via query param is rejected."""

    dep = get_current_user(allow_upload_token=True)

    with pytest.raises(
        HTTPException, match='Passing upload token via query parameter'
    ) as excinfo:
        dep(upload_token_query_param='abc123')
    assert excinfo.value.status_code == 400


def test_get_current_user_keycloak_token_from_cookie(monkeypatch, allowed_user):
    monkeypatch.setattr(
        'nomad.auth.keycloak.keycloak.tokenauth',
        lambda token: allowed_user,
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.datamodel.User.get',
        lambda *args, **kwargs: allowed_user,
    )

    dep = get_current_user(
        required=True,
        allow_keycloak_token=True,
    )

    # Success case
    request = Request(
        {
            'type': 'http',
            'headers': [],
            'path': '/',
            'query_string': b'',
        }
    )
    request._cookies = {'Authorization': 'Bearer abc'}
    assert dep(request=request) == allowed_user

    # Failure case: no token in cookies
    request._cookies = {}
    with pytest.raises(HTTPException, match='Authentication required.') as exc:
        dep(request=request)
    assert exc.value.status_code == 401


@pytest.mark.parametrize('required', [True, False])
def test_get_current_user_required(required):
    dep = get_current_user(required=required)

    if required:
        with pytest.raises(HTTPException, match='Authentication required.') as exc:
            dep()
        assert exc.value.status_code == 401

    else:
        assert dep() is None


def test_get_current_user_unknown_user(allowed_user, monkeypatch):
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_keycloak_token',
        lambda *args, **kwargs: allowed_user,
    )

    dep = get_current_user()
    with pytest.raises(HTTPException, match='logged in with an unknown user') as exc:
        dep(keycloak_token='abc')
    assert exc.value.status_code == 403


@pytest.mark.parametrize('tester', [None, 'tester'])
@pytest.mark.parametrize('mode', [ModeEnum.PRODUCTION, ModeEnum.DEVELOPMENT])
def test_get_current_user_assume_auth_for_username(
    tester, mode, allowed_user, monkeypatch
):
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.config.tests.assume_auth_for_username', tester
    )
    monkeypatch.setattr('nomad.app.v1.routers.auth.config.services.mode', mode)

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.datamodel.User.get',
        lambda *args, **kwargs: allowed_user,
    )

    dep = get_current_user(required=True)

    if tester is None:
        with pytest.raises(HTTPException, match='Authentication required.') as exc:
            dep()
        assert exc.value.status_code == 401

    elif mode == ModeEnum.PRODUCTION:
        with pytest.raises(ValueError, match='assume_auth_for_username is test-only'):
            dep()

    else:
        assert dep() == allowed_user


@pytest.mark.parametrize(
    'user, status_code, exc_msg',
    [
        (None, 401, 'Authentication is required for this Oasis'),
        ('not_allowed', 403, 'not authorized to access this Oasis'),
        ('allowed', 200, None),
    ],
)
def test_get_current_user_oasis_allowed_users(
    user,
    status_code: int,
    exc_msg: str,
    allowed_user,
    monkeypatch,
):
    if user == 'allowed':
        auth_user = allowed_user
    elif user == 'not_allowed':
        auth_user = User(
            user_id='456', username='not_allowed', email='notallowed@example.com'
        )
    else:
        auth_user = None

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.config.oasis.allowed_users', ['tester']
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_keycloak_token',
        lambda *args, **kwargs: auth_user,
    )

    dep = get_current_user(required=False)

    if status_code != 200:
        with pytest.raises(HTTPException, match=exc_msg) as exc:
            dep(keycloak_token='abc')
        assert exc.value.status_code == status_code

    else:
        monkeypatch.setattr(
            'nomad.app.v1.routers.auth.datamodel.User.get',
            lambda *args, **kwargs: allowed_user,
        )
        assert dep(keycloak_token='abc') == allowed_user
