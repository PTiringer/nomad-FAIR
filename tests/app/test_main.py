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

import re
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.testclient import TestClient

from nomad.app.main import OASIS_AUTH_WHITELIST, OasisAuthenticationMiddleware
from nomad.infrastructure import KeycloakError

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
    whitelist_patterns, request_path, expected_status, expected_text, monkeypatch
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

    monkeypatch.setattr('nomad.config.oasis.require_authentication', True)

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
    monkeypatch.setattr('nomad.config.oasis.require_authentication', True)

    def mock_tokenauth(token):
        raise KeycloakError('Invalid token')

    monkeypatch.setattr('nomad.infrastructure.keycloak.tokenauth', mock_tokenauth)

    response = app_middleware_client.get(
        '/protected', headers={'Authorization': 'Bearer invalid'}
    )

    assert response.status_code == 401
    assert response.text == 'Invalid access token.'


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.email = 'someone@example.com'
    return user


def test_oasis_auth_middleware_user_not_allowed(
    app_middleware_client, monkeypatch, mock_user
):
    monkeypatch.setattr('nomad.config.oasis.require_authentication', True)
    monkeypatch.setattr(
        'nomad.infrastructure.keycloak.tokenauth', lambda token: mock_user
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
    monkeypatch.setattr('nomad.config.oasis.require_authentication', True)
    monkeypatch.setattr(
        'nomad.infrastructure.keycloak.tokenauth', lambda token: mock_user
    )
    monkeypatch.setattr('nomad.config.oasis.allowed_users', {mock_user.email})
    response = app_middleware_client.get(
        '/protected', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == 200
    assert response.text == 'protected endpoint'


# Tests for `/alive`, `/-/health` and static files app (`/docs` and `/gui`)


@pytest.mark.parametrize('require_auth', [True, False])
def test_alive_health(monkeypatch, client, require_auth):
    monkeypatch.setattr('nomad.config.oasis.require_authentication', require_auth)

    assert client.get('/alive').status_code == 200
    assert client.get('/-/health').status_code == 200


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


# Integration tests to verify `OasisAuthenticationMiddleware` is applied correctly


def collect_all_routes(
    app: FastAPI, prefix: str = ''
) -> tuple[list[tuple[str, str, Route]], list[tuple[str, str, Route]]]:
    """
    Recursively collects all (method, full_path, route) tuples from a FastAPI app.

    Returns:
        (protected_routes, always_open_routes) based on whitelist matching.
    """

    def infer_app_name_from_path(path: str) -> str:
        if path.startswith('/api/v1'):
            return 'v1_app'
        elif path.startswith('/optimade'):
            return 'optimade_app'
        elif path.startswith('/dcat'):
            return 'dcat_app'
        elif path.startswith('/h5grove'):
            return 'h5grove_app'
        elif path.startswith('/resources'):
            return 'resources_app'

        return 'main_app'

    protected_routes = []
    whitelisted_routes = []

    for route in app.router.routes:
        full_path = prefix + getattr(route, 'path', '')

        if isinstance(route, APIRoute | Route):
            method: str = sorted(route.methods)[0]  # one method each endpoint
            app_name: str = infer_app_name_from_path(full_path)

            # `main_app` should not be affected by this auth middleware
            if app_name == 'main_app' or any(
                re.search(pattern, full_path)
                for pattern in OASIS_AUTH_WHITELIST[app_name]
            ):
                whitelisted_routes.append((method, full_path, route))
            else:
                protected_routes.append((method, full_path, route))

        elif isinstance(route, Mount):
            subapp = route.app
            if isinstance(subapp, FastAPI):
                sub_protected, sub_whitelisted = collect_all_routes(subapp, full_path)
                protected_routes.extend(sub_protected)
                whitelisted_routes.extend(sub_whitelisted)

        else:
            raise ValueError(f'Unknown {type(route)=}')

    return protected_routes, whitelisted_routes


@pytest.fixture(scope='function')
def route_collections(client, monkeypatch) -> dict[str, list[tuple[str, str, Route]]]:
    monkeypatch.setattr('nomad.config.config.oasis.require_authentication', True)

    protected_routes, always_open_routes = collect_all_routes(client.app)
    return {'protected': protected_routes, 'whitelisted': always_open_routes}


def test_all_protected_endpoints(client, route_collections, monkeypatch):
    monkeypatch.setattr('nomad.config.oasis.require_authentication', True)

    protected_routes = route_collections['protected']

    failures: list[str] = []
    for method, path, _ in protected_routes:
        method_func = {
            'GET': client.get,
            'POST': client.post,
            'PUT': client.put,
            'DELETE': client.delete,
            'HEAD': client.head,
        }.get(method)

        if method_func is None:
            failures.append(f'Unsupported HTTP {method=} for {path=}')
            continue

        try:
            response = method_func(path)
            if response.status_code != 401:
                failures.append(
                    f'Expected 401 for {method} {path}, but got {response.status_code}.\n'
                    f'Response: {response.text}'
                )
        except Exception as e:
            failures.append(f'Error testing {method} {path}: {str(e)}')

    if failures:
        pytest.fail('\n'.join(failures))


def test_all_whitelisted_endpoints(client, route_collections, monkeypatch):
    monkeypatch.setattr('nomad.config.oasis.require_authentication', True)

    whitelisted_routes = route_collections['whitelisted']

    failures: list[str] = []
    for method, path, _ in whitelisted_routes:
        if method == 'GET':
            try:
                response = client.get(path)
                if response.status_code not in {200, 404}:
                    failures.append(
                        f'Expected 200 or 404 for GET {path}, but got {response.status_code}. '
                        f'Response: {response.text}'
                    )
            except Exception as e:
                failures.append(f'Error testing GET {path}: {str(e)}')

    if failures:
        pytest.fail('\n'.join(failures))
