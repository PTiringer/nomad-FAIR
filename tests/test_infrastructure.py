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

import time
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from keycloak import KeycloakAuthenticationError

from nomad.datamodel import User
from nomad.infrastructure import Keycloak, KeycloakError, UserManagement
from tests.fixtures.users import fake_user_uuid

# Tests for `OasisUserManagement`


@pytest.fixture(scope='function')
def user_management(api_v1):
    from nomad.infrastructure import OasisUserManagement

    return OasisUserManagement('users')


@pytest.mark.parametrize(
    'query,count',
    [
        pytest.param('Sheldon', 1, id='exists'),
        pytest.param('Does not exist $%&#', 0, id='does-not-exist'),
    ],
)
def test_search_user(user_management: UserManagement, query, count):
    users = user_management.search_user(query)
    assert len(users) == count


@pytest.mark.parametrize(
    'key,value',
    [
        pytest.param('username', 'scooper', id='username'),
        pytest.param('email', 'sheldon.cooper@nomad-coe.eu', id='email'),
        pytest.param('user_id', fake_user_uuid(1), id='user_id'),
    ],
)
def test_get_user(user_management: UserManagement, key, value):
    user = user_management.get_user(**{key: value})
    assert user is not None
    assert getattr(user, key) == (value if key != 'email' else None)


def test_get_admin_user(monkeypatch, user_management: UserManagement):
    user = user_management.get_user(username='scooper')
    assert user is not None
    monkeypatch.setattr('nomad.config.services.admin_user_id', user.user_id)
    assert user.is_admin


# Tests for `Keycloak`


@pytest.fixture
def rsa_keys():
    """Generate private/public RSA keys for RS256 test tokens."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    public_pem = public_key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return private_key, public_pem


def test_basicauth_success(monkeypatch):
    kc = Keycloak()

    mock_client = Mock()
    mock_client.token.return_value = {
        'access_token': 'ACCESS',
        'refresh_token': 'REFRESH',
        'token_type': 'Bearer',
        'expires_in': 300,
    }

    monkeypatch.setattr(kc, '_Keycloak__oidc_client', mock_client)

    token = kc.basicauth('alice', 'password')

    assert token.access_token == 'ACCESS'
    assert token.refresh_token == 'REFRESH'
    assert token.token_type == 'Bearer'


def test_basicauth_failure(monkeypatch):
    kc = Keycloak()

    mock_client = Mock()
    mock_client.token.side_effect = KeycloakAuthenticationError('bad creds')

    monkeypatch.setattr(kc, '_Keycloak__oidc_client', mock_client)

    with pytest.raises(KeycloakError, match='bad creds'):
        kc.basicauth('alice', 'wrong')


def test_refresh_token(monkeypatch):
    kc = Keycloak()

    mock_client = Mock()
    mock_client.refresh_token.return_value = {
        'access_token': 'NEW',
        'refresh_token': 'NEW_REFRESH',
        'token_type': 'Bearer',
        'expires_in': 300,
    }

    monkeypatch.setattr(kc, '_Keycloak__oidc_client', mock_client)

    token = kc.refresh_token('OLD_REFRESH')

    assert token.access_token == 'NEW'
    assert token.token_type == 'Bearer'


def test_tokenauth_success(monkeypatch):
    kc = Keycloak()

    fake_payload = {
        'sub': 'user999',
        'preferred_username': 'alice',
        'email': 'a@example.com',
        'given_name': 'Alice',
        'family_name': 'Doe',
    }

    monkeypatch.setattr(kc, 'decode_access_token', lambda token: fake_payload)

    user = kc.tokenauth('TOKEN')

    assert isinstance(user, User)
    assert user.user_id == 'user999'
    assert user.username == 'alice'


def test_tokenauth_missing_sub(monkeypatch):
    kc = Keycloak()

    monkeypatch.setattr(kc, 'decode_access_token', lambda token: {'email': 'x@x.com'})

    with pytest.raises(KeycloakError, match='given token does not contain a user_id'):
        kc.tokenauth('TOKEN')


@pytest.mark.parametrize(
    'payload,issuer_config,expected_cause',
    [
        # Expired token
        (
            {
                'sub': 'user1',
                'exp': int(time.time()) - 1000,
                'iat': int(time.time()) - 2000,
                'iss': 'https://issuer.example',
            },
            'https://issuer.example',
            jwt.ExpiredSignatureError,
        ),
        # nbf (not before) in future
        (
            {
                'sub': 'user1',
                'nbf': int(time.time()) + 5000,
                'iat': int(time.time()),
                'exp': int(time.time()) + 6000,
                'iss': 'issuer',
            },
            'issuer',
            jwt.ImmatureSignatureError,
        ),
        # Wrong issuer
        (
            {
                'sub': 'user1',
                'iat': int(time.time()),
                'exp': int(time.time()) + 300,
                'iss': 'WRONG-ISSUER',
            },
            'correct-issuer',
            jwt.InvalidIssuerError,
        ),
        # Ignore audience (success)
        (
            {
                'sub': 'user123',
                'aud': 'BAD-AUD',
                'iat': int(time.time()),
                'exp': int(time.time()) + 300,
                'iss': 'https://issuer.example',
            },
            'https://issuer.example',
            None,  # Success expected
        ),
    ],
)
def test_decode_access_token_parametrized(
    monkeypatch, rsa_keys, payload, issuer_config, expected_cause
):
    kc = Keycloak()
    private_key, public_pem = rsa_keys

    monkeypatch.setattr(kc, '_Keycloak__public_keys', {'kid123': public_pem})
    monkeypatch.setattr(jwt, 'get_unverified_header', lambda t: {'kid': 'kid123'})

    class FakeOIDC:
        def well_known(self):
            return {'issuer': issuer_config}

    monkeypatch.setattr(kc, '_Keycloak__oidc_client', FakeOIDC())

    token = jwt.encode(
        payload,
        private_key,
        algorithm='RS256',
        headers={'kid': 'kid123'},
    )

    # Success case
    if expected_cause is None:
        decoded = kc.decode_access_token(token)
        # check that essential fields match
        for k, v in payload.items():
            assert decoded[k] == v
        return

    # Failure case
    with pytest.raises(KeycloakError) as exc:
        kc.decode_access_token(token)
    assert isinstance(exc.value.__cause__, expected_cause)
