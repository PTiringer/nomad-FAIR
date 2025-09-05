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
from datetime import timezone

from fastapi_cache import FastAPICache

import nomad.mongo.cache as cache_module
from nomad.common import now


def assert_info(client):
    rv = client.get('info')
    assert rv.status_code == 200
    data = rv.json()
    assert 'codes' in data
    assert 'parsers' in data
    assert 'statistics' in data
    assert len(data['parsers']) >= len(data['codes'])


def get_cached():
    mongo_backend = cache_module.MongoBackend()
    return mongo_backend._get_cached('::087b452df0dbc495df6fcbe9466c55d8')


def test_info(monkeypatch, client, mongo_function, elastic_function):
    # We do not test expiration of the info cache because we cannot force mongoDB to
    # check for expired documents and we do not want to wait for 60+ seconds until it
    # happens on its own.

    FastAPICache.init(cache_module.MongoBackend())
    noon = now().replace(hour=12, minute=34, second=56, microsecond=789000)
    morning = noon.replace(hour=6)
    evening = noon.replace(hour=18)

    monkeypatch.setattr(cache_module, 'now', lambda: morning)
    assert_info(client)
    cached = get_cached()
    assert cached['create_time'].replace(tzinfo=timezone.utc) == morning

    # cache is still valid (and wouldn't expire fast enough anyway)
    monkeypatch.setattr(cache_module, 'now', lambda: noon)
    assert_info(client)
    cached = get_cached()
    assert cached['create_time'].replace(tzinfo=timezone.utc) == morning

    # forcing cache miss
    get_cached().delete()
    monkeypatch.setattr(cache_module, 'now', lambda: evening)
    assert_info(client)
    cached = get_cached()
    assert cached['create_time'].replace(tzinfo=timezone.utc) == evening
