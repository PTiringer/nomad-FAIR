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

import numpy as np
import pytest

from nomad.graph.graph_reader import DefinitionReader
from nomad.metainfo import (
    MSection,
    Package,
    Quantity,
    Reference,
    SectionProxy,
    SubSection,
)

m_package = Package()


class Inner(MSection):
    n_impurities = Quantity(type=np.int32)


class Base(MSection):
    dimensionality = Quantity(type=np.int32)

    n_points = Quantity(type=np.int32)


class Derived(Base):
    weights = Quantity(type=np.float64, shape=['*'])

    inner = Quantity(type=Reference(SectionProxy('Inner')))


class Holder(MSection):
    base = Quantity(type=Reference(SectionProxy('Base')), shape=[])

    derived = Quantity(type=Reference(SectionProxy('Derived')), shape=[])

    derived_section = SubSection(sub_section=Derived.m_def)


m_package.init_metainfo()

m_def = Holder.m_def

prefix = 'metainfo/tests.graph.test_definition_reader/section_definitions'


def remove_cache(result):
    if '__CACHE__' in result:
        del result['__CACHE__']
    return result


def assert_list(l1, l2):
    assert len(l1) == len(l2)
    for i, j in zip(l1, l2):
        if isinstance(i, dict):
            assert_dict(i, j)
        elif isinstance(i, list):
            assert_list(i, j)
        else:
            assert i == j


def assert_dict(d1, d2):
    # we do not check if the definition_id/m_def_id is exactly the same
    # as the slightest change made here and there will result in a different ID
    # only check the existence to make maintenance easier
    d1_keys = set(d1.keys())
    if 'm_def_id' in d1_keys:
        assert 'm_def' in d1
        d1_keys.remove('m_def_id')
    assert d1_keys == set(d2.keys())
    for k in d1_keys:
        v = d1[k]
        if k == 'definition_id':
            assert k in d2
        elif isinstance(v, dict):
            assert_dict(v, d2[k])
        elif isinstance(v, list):
            assert_list(v, d2[k])
        else:
            assert v == d2[k]


@pytest.mark.parametrize(
    'query,result',
    [
        # plain get default quantities
        # the references are not resolved
        pytest.param(
            {'m_request': {'directive': 'plain'}},
            {
                'm_def': f'{prefix}/3',
                'metainfo': {
                    'tests.graph.test_definition_reader': {
                        'section_definitions': [
                            None,
                            None,
                            None,
                            {
                                'name': 'Holder',
                                'quantities': [
                                    {
                                        'name': 'base',
                                        'shape': [],
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/1',
                                        },
                                        'definition_id': '2e90eaff57224868b2d8a7b5a1ef4f51f661aefb',
                                    },
                                    {
                                        'name': 'derived',
                                        'shape': [],
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/2',
                                        },
                                        'definition_id': 'bce3fd28f47edfedf21980b553bbd68163b84212',
                                    },
                                ],
                                'sub_sections': [
                                    {
                                        'name': 'derived_section',
                                        'sub_section': f'{prefix}/2',
                                        'definition_id': 'ad5b9321c87668f404d99bdc95976f21cab69562',
                                    }
                                ],
                                'definition_id': 'b7675bcdc8a25f171961a8e3b85ece9e59c6e999',
                            },
                        ]
                    }
                },
            },
            id='plain-retrieval',
        ),
        pytest.param(
            {
                'm_request': {
                    'directive': 'plain',
                    'exclude': ['*test_definition_reader*'],
                }
            },
            {'m_def': f'{prefix}/3'},
            id='plain-retrieval-exclude',
        ),
        # now resolve all referenced quantities and sections
        pytest.param(
            {'m_request': {'directive': 'resolved'}},
            {
                'm_def': f'{prefix}/3',
                'metainfo': {
                    'tests.graph.test_definition_reader': {
                        'section_definitions': [
                            {
                                'name': 'Inner',
                                'quantities': [
                                    {
                                        'name': 'n_impurities',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': '77711c525a6b448c7b38cbce02762eff0fa36666',
                                    }
                                ],
                                'definition_id': '47c417480d4b9de8aa246adda72b851d7be8bc53',
                            },
                            {
                                'name': 'Base',
                                'quantities': [
                                    {
                                        'name': 'dimensionality',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': '5c3ae225c80c8ef5f36dfd337501d2e5c23508a0',
                                    },
                                    {
                                        'name': 'n_points',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': 'b08da41772eab4e57065765121cfc141d2a49126',
                                    },
                                ],
                                'definition_id': '5948767827ba6a72947d0ef6fddc813604aaf326',
                            },
                            {
                                'name': 'Derived',
                                'base_sections': [f'{prefix}/1'],
                                'quantities': [
                                    {
                                        'name': 'inner',
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/0',
                                        },
                                        'definition_id': '79576fa3daa3dc828511d41feb4a19e750b2b805',
                                    },
                                    {
                                        'name': 'weights',
                                        'shape': ['*'],
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'float64',
                                        },
                                        'definition_id': 'bab4bd7bdcf8d0b60efb07b96a5b5ba0d04ec988',
                                    },
                                ],
                                'definition_id': '3d31b34a5bea2a7a100989df5292bcf3f8e98194',
                            },
                            {
                                'name': 'Holder',
                                'quantities': [
                                    {
                                        'name': 'base',
                                        'shape': [],
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/1',
                                        },
                                        'definition_id': '2e90eaff57224868b2d8a7b5a1ef4f51f661aefb',
                                    },
                                    {
                                        'name': 'derived',
                                        'shape': [],
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/2',
                                        },
                                        'definition_id': 'bce3fd28f47edfedf21980b553bbd68163b84212',
                                    },
                                ],
                                'sub_sections': [f'{prefix}/2'],
                                'definition_id': 'b7675bcdc8a25f171961a8e3b85ece9e59c6e999',
                            },
                        ]
                    }
                },
            },
            id='resolve-all',
        ),
        # limit resolve depth via depth
        # as a result, inner is not resolved
        pytest.param(
            {'m_request': {'directive': 'resolved', 'depth': 1}},
            {
                'm_def': f'{prefix}/3',
                'metainfo': {
                    'tests.graph.test_definition_reader': {
                        'section_definitions': [
                            None,
                            {
                                'name': 'Base',
                                'quantities': [
                                    {
                                        'name': 'dimensionality',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': '5c3ae225c80c8ef5f36dfd337501d2e5c23508a0',
                                    },
                                    {
                                        'name': 'n_points',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': 'b08da41772eab4e57065765121cfc141d2a49126',
                                    },
                                ],
                                'definition_id': '5948767827ba6a72947d0ef6fddc813604aaf326',
                            },
                            {
                                'name': 'Derived',
                                'base_sections': [f'{prefix}/1'],
                                'quantities': [
                                    {
                                        'name': 'inner',
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/0',
                                        },
                                        'definition_id': '79576fa3daa3dc828511d41feb4a19e750b2b805',
                                    },
                                    {
                                        'name': 'weights',
                                        'shape': ['*'],
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'float64',
                                        },
                                        'definition_id': 'bab4bd7bdcf8d0b60efb07b96a5b5ba0d04ec988',
                                    },
                                ],
                                'definition_id': '3d31b34a5bea2a7a100989df5292bcf3f8e98194',
                            },
                            {
                                'name': 'Holder',
                                'quantities': [
                                    {
                                        'name': 'base',
                                        'shape': [],
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/1',
                                        },
                                        'definition_id': '2e90eaff57224868b2d8a7b5a1ef4f51f661aefb',
                                    },
                                    {
                                        'name': 'derived',
                                        'shape': [],
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/2',
                                        },
                                        'definition_id': 'bce3fd28f47edfedf21980b553bbd68163b84212',
                                    },
                                ],
                                'sub_sections': [f'{prefix}/2'],
                                'definition_id': 'b7675bcdc8a25f171961a8e3b85ece9e59c6e999',
                            },
                        ]
                    }
                },
            },
            id='resolve-with-depth',
        ),
        pytest.param(
            {
                'all_quantities': {'m_request': {'directive': 'plain'}},
                'inherited_sections': {'m_request': {'directive': 'plain'}},
                'all_base_sections': {'m_request': {'directive': 'plain'}},
            },
            {
                'm_def': f'{prefix}/3',
                'metainfo': {
                    'tests.graph.test_definition_reader': {
                        'section_definitions': [
                            None,
                            None,
                            None,
                            {
                                'all_quantities': {
                                    'base': f'{prefix}/3/quantities/0',
                                    'derived': f'{prefix}/3/quantities/1',
                                },
                                'inherited_sections': [f'{prefix}/3'],
                                'all_base_sections': [],
                            },
                        ]
                    }
                },
            },
            id='get-derived-only',
        ),
        # resolve all quantities
        pytest.param(
            {'all_quantities': {'m_request': {'directive': 'resolved'}}},
            {
                'm_def': f'{prefix}/3',
                'metainfo': {
                    'tests.graph.test_definition_reader': {
                        'section_definitions': [
                            {
                                'name': 'Inner',
                                'quantities': [
                                    {
                                        'name': 'n_impurities',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': '77711c525a6b448c7b38cbce02762eff0fa36666',
                                    }
                                ],
                                'definition_id': '47c417480d4b9de8aa246adda72b851d7be8bc53',
                            },
                            {
                                'name': 'Base',
                                'quantities': [
                                    {
                                        'name': 'dimensionality',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': '5c3ae225c80c8ef5f36dfd337501d2e5c23508a0',
                                    },
                                    {
                                        'name': 'n_points',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': 'b08da41772eab4e57065765121cfc141d2a49126',
                                    },
                                ],
                                'definition_id': '5948767827ba6a72947d0ef6fddc813604aaf326',
                            },
                            {
                                'name': 'Derived',
                                'base_sections': [f'{prefix}/1'],
                                'quantities': [
                                    {
                                        'name': 'inner',
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/0',
                                        },
                                        'definition_id': '79576fa3daa3dc828511d41feb4a19e750b2b805',
                                    },
                                    {
                                        'name': 'weights',
                                        'shape': ['*'],
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'float64',
                                        },
                                        'definition_id': 'bab4bd7bdcf8d0b60efb07b96a5b5ba0d04ec988',
                                    },
                                ],
                                'definition_id': '3d31b34a5bea2a7a100989df5292bcf3f8e98194',
                            },
                            {
                                'all_quantities': {
                                    'base': f'{prefix}/3/quantities/0',
                                    'derived': f'{prefix}/3/quantities/1',
                                },
                                'quantities': [
                                    {
                                        'name': 'base',
                                        'shape': [],
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/1',
                                        },
                                        'definition_id': '2e90eaff57224868b2d8a7b5a1ef4f51f661aefb',
                                    },
                                    {
                                        'name': 'derived',
                                        'shape': [],
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/2',
                                        },
                                        'definition_id': 'bce3fd28f47edfedf21980b553bbd68163b84212',
                                    },
                                ],
                            },
                        ]
                    }
                },
            },
            id='get-derived-resolved',
        ),
        pytest.param(
            {'all_quantities': {'m_request': {'directive': 'resolved', 'depth': 1}}},
            {
                'm_def': f'{prefix}/3',
                'metainfo': {
                    'tests.graph.test_definition_reader': {
                        'section_definitions': [
                            None,
                            {
                                'name': 'Base',
                                'quantities': [
                                    {
                                        'name': 'dimensionality',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': '5c3ae225c80c8ef5f36dfd337501d2e5c23508a0',
                                    },
                                    {
                                        'name': 'n_points',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': 'b08da41772eab4e57065765121cfc141d2a49126',
                                    },
                                ],
                                'definition_id': '5948767827ba6a72947d0ef6fddc813604aaf326',
                            },
                            {
                                'name': 'Derived',
                                'base_sections': [f'{prefix}/1'],
                                'quantities': [
                                    {
                                        'name': 'inner',
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/0',
                                        },
                                        'definition_id': '79576fa3daa3dc828511d41feb4a19e750b2b805',
                                    },
                                    {
                                        'name': 'weights',
                                        'shape': ['*'],
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'float64',
                                        },
                                        'definition_id': 'bab4bd7bdcf8d0b60efb07b96a5b5ba0d04ec988',
                                    },
                                ],
                                'definition_id': '3d31b34a5bea2a7a100989df5292bcf3f8e98194',
                            },
                            {
                                'all_quantities': {
                                    'base': f'{prefix}/3/quantities/0',
                                    'derived': f'{prefix}/3/quantities/1',
                                },
                                'quantities': [
                                    {
                                        'name': 'base',
                                        'shape': [],
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/1',
                                        },
                                        'definition_id': '2e90eaff57224868b2d8a7b5a1ef4f51f661aefb',
                                    },
                                    {
                                        'name': 'derived',
                                        'shape': [],
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/2',
                                        },
                                        'definition_id': 'bce3fd28f47edfedf21980b553bbd68163b84212',
                                    },
                                ],
                            },
                        ]
                    }
                },
            },
            id='get-derived-resolved-with-depth',
        ),
        pytest.param(
            {
                'all_sub_sections': {
                    'm_request': {
                        'directive': 'resolved',
                        'resolve_depth': 1,
                    }
                },
            },
            {
                'm_def': f'{prefix}/3',
                'metainfo': {
                    'tests.graph.test_definition_reader': {
                        'section_definitions': [
                            {
                                'name': 'Inner',
                                'quantities': [
                                    {
                                        'name': 'n_impurities',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': '77711c525a6b448c7b38cbce02762eff0fa36666',
                                    }
                                ],
                                'definition_id': '47c417480d4b9de8aa246adda72b851d7be8bc53',
                            },
                            {
                                'name': 'Base',
                                'quantities': [
                                    {
                                        'name': 'dimensionality',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': '5c3ae225c80c8ef5f36dfd337501d2e5c23508a0',
                                    },
                                    {
                                        'name': 'n_points',
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'int32',
                                        },
                                        'definition_id': 'b08da41772eab4e57065765121cfc141d2a49126',
                                    },
                                ],
                                'definition_id': '5948767827ba6a72947d0ef6fddc813604aaf326',
                            },
                            {
                                'name': 'Derived',
                                'base_sections': [f'{prefix}/1'],
                                'quantities': [
                                    {
                                        'name': 'inner',
                                        'type': {
                                            'type_kind': 'reference',
                                            'type_data': f'{prefix}/0',
                                        },
                                        'definition_id': '79576fa3daa3dc828511d41feb4a19e750b2b805',
                                    },
                                    {
                                        'name': 'weights',
                                        'shape': ['*'],
                                        'type': {
                                            'type_kind': 'numpy',
                                            'type_data': 'float64',
                                        },
                                        'definition_id': 'bab4bd7bdcf8d0b60efb07b96a5b5ba0d04ec988',
                                    },
                                ],
                                'definition_id': '3d31b34a5bea2a7a100989df5292bcf3f8e98194',
                            },
                            {'all_sub_sections': {'derived_section': f'{prefix}/2'}},
                        ]
                    }
                },
            },
            id='get-derived-subsection',
        ),
    ],
)
def test_definition_reader(query: dict, result: dict):
    with DefinitionReader(query) as reader:
        response = remove_cache(reader.sync_read(m_def))
        assert_dict(response, result)
