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
from pydantic import ValidationError

from nomad.datamodel.data import Query
from nomad.metainfo.metainfo import MSection, Quantity


@pytest.mark.parametrize(
    'query,valid',
    [
        # 'and' query operator naming in serialization
        [
            {
                'query': {'and': [{'x': 'y'}, {'x': 'z'}]},
                'pagination': {'total': 0},
                'data': [],
            },
            True,
        ],
        # 'or' query operator naming in serialization
        [
            {
                'query': {'or': [{'x': 'y'}, {'x': 'z'}]},
                'pagination': {'total': 0},
                'data': [],
            },
            True,
        ],
        # invalid data
        [
            {'invalid': 'data'},
            False,
        ],
    ],
)
def test_query_normalization(query, valid):
    """Tests normalization in serialization + de-serialization."""

    def test(query):
        class TestSection(MSection):
            a = Quantity(type=Query)

        b = TestSection()
        b.a = query
        b.m_from_dict(b.m_to_dict())

    if valid:
        test(query)
    else:
        with pytest.raises(ValidationError):
            test(query)
