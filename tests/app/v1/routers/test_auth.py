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
from nomad.auth.scopes import Scope
from nomad.auth.tokens import AuthResult
from nomad.config.models.config import ModeEnum

# Tests for OIDC authentication endpoints


@pytest.mark.parametrize(
    'form_data, expected_status',
    [
        pytest.param(
            dict(username='user1', password='password', grant_type='password'),
            200,
            id='valid-credentials',
        ),
        pytest.param(
            dict(username='bad', password='credentials', grant_type='password'),
            401,
            id='invalid-credentials',
        ),
        pytest.param(
            dict(username='user1', password='password'),
            422,
            id='missing-grant-type',
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


@pytest.mark.parametrize(
    'auth_key, expected_status',
    [
        pytest.param('user1', 200, id='authorized'),
        pytest.param(None, 401, id='no-auth'),
        pytest.param('invalid', 401, id='invalid-auth'),
    ],
)
def test_get_signature_token(auth_headers, client, auth_key, expected_status):
    headers = auth_headers.get(auth_key) if auth_key else None
    response = client.get('auth/signature_token', headers=headers)
    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.json().get('signature_token') is not None


@pytest.mark.parametrize(
    'auth_key, expires_in, expected_status',
    [
        pytest.param('user1', 0, 422, id='valid-auth-expires-too-short'),
        pytest.param('user1', 30 * 60, 200, id='valid-auth-expires-30min'),
        pytest.param('user1', 2 * 60 * 60, 200, id='valid-auth-expires-2h'),
        pytest.param('user1', 31 * 24 * 60 * 60, 422, id='valid-auth-expires-too-long'),
        pytest.param('user1', None, 422, id='valid-auth-expires-missing'),
        pytest.param(None, 60, 401, id='no-auth'),
        pytest.param('invalid', 60, 401, id='invalid-auth'),
    ],
)
def test_get_app_token(auth_headers, client, auth_key, expires_in, expected_status):
    headers = auth_headers.get(auth_key) if auth_key else None
    response = client.get(
        'auth/app_token',
        headers=headers,
        params={'expires_in': expires_in},
    )
    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.json().get('app_token') is not None


# Tests for `get_current_user`


@pytest.fixture
def allowed_user():
    return User(user_id='123', email='test@example.com', username='tester')


@pytest.fixture
def patch_user_get(monkeypatch):
    """
    Patch datamodel.User.get.

    Usage:
        patch_user_get(user)   -> User.get(...) returns user
        patch_user_get(None)   -> User.get(...) returns None
    """

    def _patch(user: User | None) -> None:
        monkeypatch.setattr(
            'nomad.app.v1.routers.auth.datamodel.User.get',
            lambda *args, **kwargs: user,
        )

    return _patch


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
    patch_user_get,
    monkeypatch,
):
    if allow_simple_token:  # ensure dummy simple token could decode as JWT
        monkeypatch.setattr(
            'nomad.app.v1.routers.auth.jwt.decode',
            lambda *args, **kwargs: {'user': allowed_user.user_id, 'exp': 600},
        )

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_keycloak_token',
        lambda _token: (
            AuthResult(allowed_user, set()) if get_user_from_keycloak_token else None
        ),
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_simple_token',
        lambda _token: (
            AuthResult(allowed_user, set()) if get_user_from_simple_token else None
        ),
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_upload_token',
        lambda _token: (
            AuthResult(allowed_user, set()) if get_user_from_upload_token else None
        ),
    )

    patch_user_get(allowed_user)

    dep = get_current_user(
        required_scopes=[],
        allow_anonymous=False,
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

    dep = get_current_user(
        required_scopes=[Scope.UPLOADS_READ], allow_upload_token=True
    )

    with pytest.raises(
        HTTPException, match='Passing upload token via query parameter'
    ) as exc:
        dep(upload_token_query_param='abc123')
    assert exc.value.status_code == 400


def test_get_current_user_keycloak_token_from_cookie(
    monkeypatch, allowed_user, patch_user_get
):
    monkeypatch.setattr(
        'nomad.auth.keycloak.keycloak.tokenauth',
        lambda _token: allowed_user,
    )
    patch_user_get(allowed_user)

    dep = get_current_user(
        required_scopes=[],
        allow_anonymous=False,
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


@pytest.mark.parametrize('allow_anonymous', [True, False])
def test_get_current_user_allow_anonymous(allow_anonymous):
    dep = get_current_user(
        required_scopes=[Scope.ENTRIES_READ], allow_anonymous=allow_anonymous
    )

    if allow_anonymous:
        assert dep() is None

    else:
        with pytest.raises(HTTPException, match='Authentication required.') as exc:
            dep()
        assert exc.value.status_code == 401


def test_get_current_user_unknown_user(allowed_user, monkeypatch):
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_keycloak_token',
        lambda _token: AuthResult(allowed_user, set()),
    )

    dep = get_current_user(required_scopes=[])
    with pytest.raises(HTTPException, match='logged in with an unknown user') as exc:
        dep(keycloak_token='abc')
    assert exc.value.status_code == 403


@pytest.mark.parametrize('tester', [None, 'tester'])
@pytest.mark.parametrize('mode', [ModeEnum.PRODUCTION, ModeEnum.DEVELOPMENT])
def test_get_current_user_assume_auth_for_username(
    tester, mode, allowed_user, patch_user_get, monkeypatch
):
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.config.tests.assume_auth_for_username', tester
    )
    monkeypatch.setattr('nomad.app.v1.routers.auth.config.services.mode', mode)

    patch_user_get(allowed_user)

    dep = get_current_user(required_scopes=[], allow_anonymous=False)

    if tester is None:
        with pytest.raises(HTTPException, match='Authentication required.') as exc:
            dep()
        assert exc.value.status_code == 401

    elif mode == ModeEnum.PRODUCTION:
        with pytest.raises(
            ValueError, match='assume_auth_for_username is development-only'
        ):
            dep()

    else:
        assert dep() == allowed_user


@pytest.mark.parametrize(
    'user, required_scopes, require_authentication, reject_unauthorized_users, authorized_users, status_code, exc_msg',
    [
        pytest.param(
            'tester',
            [],
            True,
            True,
            ['tester'],
            200,
            None,
            id='authenticated-user-in-allowed-users',
        ),
        pytest.param(
            'tester',
            [],
            True,
            True,
            ['my-user'],
            403,
            'You are not authorized to access this Oasis',
            id='authenticated-user-not-in-allowed-users',
        ),
        pytest.param(
            'tester',
            [],
            True,
            False,
            ['my-user'],
            200,
            None,
            id='authenticated-user-no-authorization-required',
        ),
        pytest.param(
            None,
            [],
            True,
            True,
            ['tester'],
            401,
            'Authentication required',
            id='unauthenticated-user-authentication-required',
        ),
        pytest.param(
            None,
            [],
            False,
            True,
            None,
            200,
            None,
            id='unauthenticated-user-authentication-not-required',
        ),
        pytest.param(
            None,
            ['uploads:read'],
            False,
            True,
            None,
            403,
            'Missing scopes:',
            id='unauthenticated-user-authentication-not-required-invalid-scope',
        ),
    ],
)
def test_get_current_user(
    user,
    required_scopes: list[str],
    require_authentication: bool,
    reject_unauthorized_users: bool,
    authorized_users: list[str],
    status_code: int,
    exc_msg: str,
    allowed_user,
    patch_user_get,
    monkeypatch,
):
    if user == 'tester':
        auth_user = allowed_user
    elif user is None:
        auth_user = None
    else:
        raise ValueError(f'Invalid user value: {user}')

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.config.auth.require_authentication',
        require_authentication,
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.config.auth.reject_unauthorized_users',
        reject_unauthorized_users,
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.config.auth.authorized_users', authorized_users
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_keycloak_token',
        lambda _token: AuthResult(auth_user, set()),
    )
    if auth_user is not None:
        patch_user_get(auth_user)

    dep = get_current_user(required_scopes=required_scopes)

    if status_code != 200:
        with pytest.raises(HTTPException, match=exc_msg) as exc:
            dep(keycloak_token='abc')
        assert exc.value.status_code == status_code
    else:
        patch_user_get(allowed_user)
        reveived_user = dep(keycloak_token='abc')
        if user is not None:
            assert reveived_user == allowed_user


# Tests for scope enforcing (`_resolve_user_with_scopes`)

# Anonymous users


def test_scopes_anonymous_allowed_with_permission(monkeypatch):
    """
    Anonymous user should be allowed when allow_anonymous=True and
    unauthenticated_user_scopes contains the required scopes.
    """

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.config.auth.unauthenticated_user_scopes',
        {'include': [Scope.BASIC_READ]},
    )

    dep = get_current_user(required_scopes=[Scope.BASIC_READ], allow_anonymous=True)

    assert dep() is None


def test_scopes_anonymous_not_allowed(monkeypatch):
    """
    Anonymous user should be rejected when not allow_anonymous.
    """

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.config.auth.unauthenticated_user_scopes',
        {'include': [Scope.BASIC_READ]},
    )

    dep = get_current_user(required_scopes=[Scope.BASIC_READ], allow_anonymous=False)

    with pytest.raises(HTTPException, match='Authentication required') as exc:
        dep()
    assert exc.value.status_code == 401


# Authenticated user


def test_scopes_authenticated_missing_scope(monkeypatch, allowed_user, patch_user_get):
    """
    Authenticated user should be forbidden (403) when scopes do not include required scopes.
    """
    patch_user_get(allowed_user)
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_keycloak_token',
        lambda _token: AuthResult(allowed_user, {Scope.BASIC_READ}),
    )

    dep = get_current_user(
        required_scopes=[Scope.GROUPS_READ],
        allow_anonymous=False,
        allow_keycloak_token=True,
    )

    with pytest.raises(HTTPException, match='Missing scopes') as exc:
        dep(keycloak_token='abc')
    assert exc.value.status_code == 403
    assert Scope.GROUPS_READ in str(exc.value.detail)


def test_scopes_authenticated_success(monkeypatch, allowed_user, patch_user_get):
    """
    Authenticated user should succeed when required scopes are present.
    """
    patch_user_get(allowed_user)
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_keycloak_token',
        lambda _token: AuthResult(allowed_user, {Scope.GROUPS_READ}),
    )

    dep = get_current_user(
        required_scopes=[Scope.GROUPS_READ],
        allow_anonymous=False,
        allow_keycloak_token=True,
    )

    assert dep(keycloak_token='abc') == allowed_user


# Scopes for simple/upload tokens


def test_scopes_simple_token_missing_scope(monkeypatch, allowed_user, patch_user_get):
    patch_user_get(allowed_user)

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.jwt.decode',
        lambda *args, **kwargs: {'user': allowed_user.user_id, 'exp': 600},
    )

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_simple_token',
        lambda _token: AuthResult(allowed_user, {Scope.BASIC_READ}),
    )

    dep = get_current_user(
        required_scopes=[Scope.TOKENS_CREATE],
        allow_anonymous=False,
        allow_keycloak_token=False,
        allow_simple_token=True,
        allow_upload_token=False,
    )

    with pytest.raises(HTTPException, match='Missing scopes') as exc:
        dep(simple_token='dummy-simple-token')
    assert exc.value.status_code == 403
    assert Scope.TOKENS_CREATE in str(exc.value.detail)


def test_scopes_simple_token_success(monkeypatch, allowed_user, patch_user_get):
    patch_user_get(allowed_user)

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.jwt.decode',
        lambda *args, **kwargs: {'user': allowed_user.user_id, 'exp': 600},
    )
    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_simple_token',
        lambda _token: AuthResult(allowed_user, {Scope.GROUPS_READ}),
    )

    dep = get_current_user(
        required_scopes=[Scope.GROUPS_READ],
        allow_anonymous=False,
        allow_keycloak_token=False,
        allow_simple_token=True,
        allow_upload_token=False,
    )

    assert dep(simple_token='dummy-simple-token') == allowed_user


def test_scopes_upload_token_allows_uploads_read(
    monkeypatch, allowed_user, patch_user_get
):
    patch_user_get(allowed_user)

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_upload_token',
        lambda _token: AuthResult(allowed_user, {Scope.UPLOADS_READ}),
    )

    dep = get_current_user(
        required_scopes=[Scope.UPLOADS_READ],
        allow_anonymous=False,
        allow_keycloak_token=False,
        allow_simple_token=False,
        allow_upload_token=True,
    )

    assert dep(upload_token='dummy-upload-token') == allowed_user


def test_scopes_upload_token_missing_non_upload_scope(
    monkeypatch, allowed_user, patch_user_get
):
    patch_user_get(allowed_user)

    monkeypatch.setattr(
        'nomad.app.v1.routers.auth.get_user_from_upload_token',
        lambda _token: AuthResult(allowed_user, {Scope.UPLOADS_READ}),
    )

    dep = get_current_user(
        required_scopes=[Scope.GROUPS_READ],
        allow_anonymous=False,
        allow_keycloak_token=False,
        allow_simple_token=False,
        allow_upload_token=True,
    )

    with pytest.raises(HTTPException, match='Missing scopes') as exc:
        dep(upload_token='dummy-upload-token')
    assert exc.value.status_code == 403
    assert Scope.GROUPS_READ in str(exc.value.detail)
