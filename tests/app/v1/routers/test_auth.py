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

from urllib.parse import urlencode

import pytest
from fastapi import HTTPException, Request

from nomad.app.v1.models.models import User
from nomad.app.v1.routers.auth import create_user_dependency


def perform_get_token_test(client, http_method, status_code, username, password):
    if http_method == 'post':
        response = client.post(
            'auth/token', data=dict(username=username, password=password)
        )
    else:
        response = client.get(
            f'auth/token?{urlencode(dict(username=username, password=password))}'
        )

    assert response.status_code == status_code


def test_post_token_success(client, user1):
    perform_get_token_test(client, 'post', 200, user1.username, 'password')


def test_post_token_bad_credentials(client):
    perform_get_token_test(client, 'post', 401, 'bad', 'credentials')


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


# Tests for `create_user_dependency`


@pytest.fixture
def allowed_user():
    return User(user_id='123', email='test@example.com', username='tester')


@pytest.mark.parametrize('bearer_token_auth_allowed', [True, False])
@pytest.mark.parametrize('upload_token_auth_allowed', [True, False])
@pytest.mark.parametrize('signature_token_auth_allowed', [True, False])
@pytest.mark.parametrize('_get_user_from_bearer_token', [True, False])
@pytest.mark.parametrize('_get_user_from_upload_token', [True, False])
@pytest.mark.parametrize('_get_user_from_signature_token', [True, False])
def test_create_user_dependency_auth_methods(
    bearer_token_auth_allowed: bool,
    upload_token_auth_allowed: bool,
    signature_token_auth_allowed: bool,
    _get_user_from_bearer_token: bool,
    _get_user_from_upload_token: bool,
    _get_user_from_signature_token: bool,
    allowed_user,
    monkeypatch,
):
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth._get_user_from_bearer_token',
        lambda *_: allowed_user if _get_user_from_bearer_token else None,
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth._get_user_from_upload_token',
        lambda *_: allowed_user if _get_user_from_upload_token else None,
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth._get_user_from_signature_token',
        lambda *_: allowed_user if _get_user_from_signature_token else None,
    )

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.datamodel.User.get',
        lambda *args, **kwargs: allowed_user,
    )

    dep = create_user_dependency(
        required=True,
        bearer_token_auth_allowed=bearer_token_auth_allowed,
        upload_token_auth_allowed=upload_token_auth_allowed,
        signature_token_auth_allowed=signature_token_auth_allowed,
    )

    if any(
        [
            bearer_token_auth_allowed and _get_user_from_bearer_token,
            upload_token_auth_allowed and _get_user_from_upload_token,
            signature_token_auth_allowed and _get_user_from_signature_token,
        ]
    ):
        assert (
            dep(
                bearer_token='abc' if bearer_token_auth_allowed else None,
                upload_token='abc' if upload_token_auth_allowed else None,
                signature_token='abc' if signature_token_auth_allowed else None,
            )
            == allowed_user
        )
    else:
        with pytest.raises(HTTPException, match='Authentication required.') as exc:
            dep()
        assert exc.value.status_code == 401


def test_create_user_dependency_rejects_query_token():
    """Ensure that passing upload token via query param is rejected."""

    dep = create_user_dependency(upload_token_auth_allowed=True)

    with pytest.raises(
        HTTPException, match='Passing upload token via query parameter'
    ) as excinfo:
        dep(upload_token_query_param='abc123')
    assert excinfo.value.status_code == 400


def test_create_user_dependency_signature_token_from_cookie(monkeypatch, allowed_user):
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.infrastructure.keycloak.tokenauth',
        lambda token: allowed_user,
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.datamodel.User.get',
        lambda *args, **kwargs: allowed_user,
    )

    dep = create_user_dependency(
        required=True,
        bearer_token_auth_allowed=False,
        upload_token_auth_allowed=False,
        signature_token_auth_allowed=True,
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
def test_create_user_dependency_required(required):
    dep = create_user_dependency(required=required)

    if required:
        with pytest.raises(HTTPException, match='Authentication required.') as exc:
            dep()
        assert exc.value.status_code == 401

    else:
        assert dep() is None


@pytest.mark.parametrize('tester', [None, 'tester'])
def test_create_user_dependency_assume_auth_for_username(
    tester, allowed_user, monkeypatch
):
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.config.tests.assume_auth_for_username', tester
    )

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.datamodel.User.get',
        lambda *args, **kwargs: allowed_user,
    )

    dep = create_user_dependency(required=True)

    if tester is None:
        with pytest.raises(HTTPException, match='Authentication required.') as exc:
            dep()
        assert exc.value.status_code == 401
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
def test_create_user_dependency_oasis_allowed_users(
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
        'nomad.app.v1.routers.auth._get_user_from_bearer_token',
        lambda *_: auth_user,
    )

    dep = create_user_dependency(required=False)

    if status_code != 200:
        with pytest.raises(HTTPException, match=exc_msg) as exc:
            dep(bearer_token='abc')
        assert exc.value.status_code == status_code

    else:
        monkeypatch.setattr(
            'nomad.app.v1.routers.auth.datamodel.User.get',
            lambda *args, **kwargs: allowed_user,
        )
        assert dep(bearer_token='abc') == allowed_user


def test_create_user_dependency_unknown_user(allowed_user, monkeypatch):
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth._get_user_from_bearer_token',
        lambda *_: allowed_user,
    )

    dep = create_user_dependency(required=False)
    with pytest.raises(HTTPException, match='logged in with an unknown user') as exc:
        dep(bearer_token='abc')
    assert exc.value.status_code == 403
