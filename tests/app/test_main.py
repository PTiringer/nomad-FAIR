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


from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from nomad.app.main import OasisAuthenticationMiddleware

# Tests for `OasisAuthenticationMiddleware`


@pytest.mark.parametrize(
    'whitelist_patterns, request_path, expected_status, expected_text',
    [
        # Exact match: allow only `/info`
        ([r'^/info$'], '/info', 200, 'I am nomad'),
        (
            [r'^/info$'],
            '/protected',
            401,
            'You have to authenticate to use this Oasis endpoint.',
        ),
        (
            [r'^/info$'],
            '/protected/info',
            401,
            'You have to authenticate to use this Oasis endpoint.',
        ),
        # Prefix match: allow `/info` and all under `/info/...`
        ([r'^/info'], '/info', 200, 'I am nomad'),
        (
            [r'^/info'],
            '/protected',
            401,
            'You have to authenticate to use this Oasis endpoint.',
        ),
        # Allow `/protected` path
        ([r'^/protected'], '/protected', 200, 'protected endpoint'),
        # Allow nested route
        ([r'^/protected/info'], '/protected/info', 200, 'I am nested'),
        # Catch-all: allow everything
        ([r'.*'], '/protected', 200, 'protected endpoint'),
        # No match at all: all endpoints require auth
        (
            [r'^/nonexistent$'],
            '/info',
            401,
            'You have to authenticate to use this Oasis endpoint.',
        ),
        (
            [r'^/nonexistent$'],
            '/protected',
            401,
            'You have to authenticate to use this Oasis endpoint.',
        ),
    ],
)
def test_oasis_auth_middleware_whitelist(
    whitelist_patterns, request_path, expected_status, expected_text
):
    def create_client():
        app = FastAPI()

        @app.get('/protected')
        async def protected():
            return PlainTextResponse('protected endpoint')

        @app.get('/info')
        async def info():
            return PlainTextResponse('I am nomad')

        @app.get('/protected/info')
        async def nested():
            return PlainTextResponse('I am nested')

        app.add_middleware(OasisAuthenticationMiddleware, whitelist=whitelist_patterns)
        return TestClient(app)

    response = create_client().get(request_path)

    assert response.status_code == expected_status
    if expected_text is not None:
        assert response.text == expected_text


@pytest.fixture
def app_middleware_client():
    """FastAPI client for testing OasisAuthenticationMiddleware."""

    def app():
        app = FastAPI()

        @app.get('/protected')
        async def protected():
            return PlainTextResponse('protected endpoint')

        @app.get('/info')
        async def info():
            return PlainTextResponse('I am nomad')

        app.add_middleware(OasisAuthenticationMiddleware, whitelist={'^/info'})
        return app

    return TestClient(app())


def test_oasis_auth_middleware_invalid_token(app_middleware_client, monkeypatch):
    monkeypatch.setattr(
        'nomad.infrastructure.keycloak.tokenauth', lambda token: (None, None)
    )
    response = app_middleware_client.get(
        '/protected', headers={'Authorization': 'Bearer invalid'}
    )
    assert response.status_code == 401
    assert response.text == 'You are not authorized to access this Oasis endpoint.'


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.email = 'someone@example.com'
    return user


def test_oasis_auth_middleware_user_not_allowed(
    app_middleware_client, monkeypatch, mock_user
):
    monkeypatch.setattr(
        'nomad.infrastructure.keycloak.tokenauth', lambda token: (mock_user, None)
    )
    monkeypatch.setattr('nomad.config.oasis.allowed_users', {})
    response = app_middleware_client.get(
        '/protected', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == 401
    assert response.text == 'You are not authorized to access this Oasis endpoint.'


def test_oasis_auth_middleware_valid_user(
    app_middleware_client, monkeypatch, mock_user
):
    monkeypatch.setattr(
        'nomad.infrastructure.keycloak.tokenauth', lambda token: (mock_user, None)
    )
    monkeypatch.setattr('nomad.config.oasis.allowed_users', {mock_user.email})
    response = app_middleware_client.get(
        '/protected', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == 200
    assert response.text == 'protected endpoint'


# Tests for `/alive`, `/-/health` and static files app (`/docs` and `/gui`)


def test_alive(client):
    rv = client.get('/alive')
    assert rv.status_code == 200


@pytest.mark.parametrize('path', ['env.js', 'artifacts.js'])
def test_gui(client, path, monkeypatch):
    monkeypatch.setattr('nomad.app.main.GuiFiles.gui_env_data', 'env.js')
    monkeypatch.setattr('nomad.app.main.GuiFiles.gui_artifacts_data', 'artifacts.js')
    monkeypatch.setattr('nomad.app.main.GuiFiles.gui_data_etag', 'etag')

    rv = client.get(f'/gui/{path}')
    assert rv.status_code == 200
    assert rv.text == path
    assert rv.headers.get('Etag') == '"etag"'

    rv = client.get(f'/gui/{path}', headers={'if-none-match': 'etag'})
    assert rv.status_code == 304

    rv = client.get(f'/gui/{path}', headers={'if-none-match': 'W/"etag"'})
    assert rv.status_code == 304

    rv = client.get(f'/gui/{path}', headers={'if-none-match': 'different-etag'})
    assert rv.status_code == 200
