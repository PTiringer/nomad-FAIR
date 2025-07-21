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
from nomad.metainfo.elasticsearch_extension import entry_type

BASE = config.services.api_base_path.rstrip('/') + '/apps'


def test_get_invalid_app_returns_404(client, no_warn):
    resp = client.get(f'{BASE}/entry-points/not-an-app')
    assert resp.status_code == 404
    body = resp.json()
    assert 'Could not find an app with the path' in body.get('detail', '')


def test_list_apps_returns_data_list(client, no_warn):
    from nomad.config.models.plugins import AppEntryPoint

    resp = client.get(f'{BASE}/entry-points')
    assert resp.status_code == 200
    data = resp.json().get('data', [])
    assert isinstance(data, list)

    apps_eps = [
        ep
        for ep in config.plugins.entry_points.filtered_values()
        if isinstance(ep, AppEntryPoint)
    ]
    expected_count = len(apps_eps)

    assert len(data) == expected_count

    returned_ids = {item['id'] for item in data}
    expected_ids = {ep.app.path for ep in apps_eps}
    assert returned_ids == expected_ids


def test_get_specific_app_returns_app_and_search_quantities(client, no_warn):
    resp = client.get(f'{BASE}/entry-points')
    apps = resp.json()['data']
    assert apps, 'Expected at least one app'
    app_id = apps[0]['id']

    resp2 = client.get(f'{BASE}/entry-points/{app_id}')
    assert resp2.status_code == 200
    body = resp2.json()
    assert 'app' in body and 'search_quantities' in body
    assert body['app']['path'] == app_id
    assert isinstance(body['search_quantities'], dict)


@pytest.mark.parametrize(
    'payload',
    [
        {},
        {'query': {}},
    ],
)
def test_search_quantities_missing_fields(client, no_warn, payload):
    resp = client.post(f'{BASE}/search-quantities', json=payload)
    assert resp.status_code == 422


def test_search_quantities_invalid_app_path(client, no_warn):
    payload = {
        'app_path': 'does-not-exist',
        'query': {'input': 'energy'},
        'pagination': {'page': 1, 'page_size': 5},
    }
    resp = client.post(f'{BASE}/search-quantities', json=payload)
    assert resp.status_code == 404
    body = resp.json()
    assert 'Could not find an app with the path' in body.get('detail', '')


def test_search_quantities_suggestions_and_exact_match(client, no_warn):
    all_q = list(entry_type.quantities.keys())
    assert all_q, 'No search quantities registered!'
    example = all_q[0]

    partial = example.split('.')[-1]
    resp = client.post(
        f'{BASE}/search-quantities',
        json={'query': {'input': partial}, 'pagination': {'page': 1, 'page_size': 10}},
    )
    assert resp.status_code == 200
    suggestions = resp.json()
    assert isinstance(suggestions, list) and suggestions

    resp2 = client.post(
        f'{BASE}/search-quantities',
        json={'query': {'input': example}, 'pagination': {'page': 1, 'page_size': 10}},
    )
    assert resp2.status_code == 200
    quantities = [item['quantity'] for item in resp2.json()]
    assert example in quantities


def test_search_quantities_filter_by_aggregatable(client, no_warn):
    resp = client.post(
        f'{BASE}/search-quantities',
        json={
            'query': {'aggregatable': True},
            'pagination': {'page': 1, 'page_size': 50},
        },
    )
    assert resp.status_code == 200
    out = resp.json()
    assert out, 'Expected some aggregatable quantities'
    assert all(item['aggregatable'] for item in out)


def test_search_quantities_pagination(client, no_warn):
    resp_full = client.post(
        f'{BASE}/search-quantities',
        json={'query': {}, 'pagination': {'page': 1, 'page_size': 1000}},
    )
    full = resp_full.json()
    total = len(full)
    if total < 2:
        pytest.skip('Not enough quantities for pagination')

    resp_p1 = client.post(
        f'{BASE}/search-quantities',
        json={'query': {}, 'pagination': {'page': 1, 'page_size': 1}},
    )
    resp_p2 = client.post(
        f'{BASE}/search-quantities',
        json={'query': {}, 'pagination': {'page': 2, 'page_size': 1}},
    )
    assert resp_p1.status_code == 200
    assert resp_p2.status_code == 200

    q1 = resp_p1.json()[0]['quantity']
    q2 = resp_p2.json()[0]['quantity']
    assert q1 != q2
