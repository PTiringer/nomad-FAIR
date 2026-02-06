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

from nomad.config.models.ui import (
    App,
    Axis,
    AxisQuantity,
    Column,
    Columns,
    RowActions,
    RowActionURL,
    RowDetails,
    Rows,
    RowSelection,
)


@pytest.mark.parametrize(
    'original, final',
    [
        pytest.param(
            {
                'options': {
                    'a': {},
                    'b': {},
                },
                'include': ['a'],
                'exclude': ['b'],
                'selected': ['a'],
            },
            [Column(quantity='a', selected=True)],
            id='columns using old model (dict)',
        ),
        pytest.param(
            Columns(
                options={
                    'a': Column(),
                    'b': Column(),
                },
                include=['a'],
                exclude=['b'],
                selected=['a'],
            ),
            [Column(quantity='a', selected=True)],
            id='columns using old model (objects)',
        ),
    ],
)
def test_columns(original, final):
    """Test the backwards compatibility of the columns field."""
    app = App(
        label='test', path='test', category='test', filter_menus={}, columns=original
    )
    assert app.columns == final


@pytest.mark.parametrize(
    'original, final',
    [
        pytest.param(
            {
                'enabled': True,
                'options': {
                    'a': {'type': 'url', 'path': 'a'},
                    'b': {'type': 'url', 'path': 'b'},
                },
                'include': ['a'],
                'exclude': ['b'],
            },
            [RowActionURL(path='a')],
            id='row actions using old model (dict)',
        ),
        pytest.param(
            RowActions(
                options={
                    'a': RowActionURL(path='a'),
                    'b': RowActionURL(path='b'),
                },
                include=['a'],
                exclude=['b'],
            ),
            [RowActionURL(path='a')],
            id='row actions old model (objects)',
        ),
    ],
)
def test_row_actions(original, final):
    """Test the backwards compatibility of the row actions field."""
    rows = Rows(
        actions=original,
        details=RowDetails(enabled=True),
        selection=RowSelection(enabled=True),
    )
    assert rows.actions.items == final


@pytest.mark.parametrize(
    'original, model',
    [
        pytest.param(
            {'unit': 'nm', 'search_quantity': 'some_molecule'},
            Axis(title=None, unit='nm', quantity=None, search_quantity='some_molecule'),
            id='Axis using old model',
        ),
        pytest.param(
            AxisQuantity(
                title=None,
                unit='nm',
                quantity=None,
                search_quantity='some_molecule',
            ),
            Axis(title=None, unit='nm', quantity=None, search_quantity='some_molecule'),
            id='Axis old model (objects)',
        ),
    ],
)
def test_axis(original, model):
    """Test the backwards compatibility of the Axis field."""

    quantity = Axis.model_validate(original)
    assert quantity == model
