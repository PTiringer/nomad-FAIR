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
from nomad.common import is_safe_relative_path, is_safe_path


@pytest.mark.parametrize(
    'path, safe_path, is_directory, is_safe',
    [
        pytest.param(
            '/safe/a', '/safe/', True, True, id='safe absolute path to folder'
        ),
        pytest.param(
            '/safe/a/../b', '/safe/', True, True, id='safe relative path to folder'
        ),
        pytest.param(
            '/unsafe/../c', '/safe/', True, False, id='unsafe absolute path to folder'
        ),
        pytest.param(
            '/safe/../unsafe',
            '/safe/',
            True,
            False,
            id='unsafe relative path to folder',
        ),
        pytest.param(
            '/safe2/',
            '/safe',
            True,
            False,
            id='unsafe absolute path to folder with same prefix',
        ),
        pytest.param(
            '/safe/safe_file.zip', '/safe/safe_file.zip', False, True, id='safe file'
        ),
        pytest.param(
            '/safe2/unsafe_file.zip',
            '/safe/safe_file.zip',
            False,
            False,
            id='unsafe file',
        ),
        pytest.param(
            '/safe2/safe_file.zip2',
            '/safe/safe_file.zip',
            False,
            False,
            id='unsafe file with same prefix',
        ),
    ],
)
def test_is_safe_path(path, safe_path, is_directory, is_safe):
    assert is_safe_path(path, safe_path, is_directory) == is_safe


@pytest.mark.parametrize(
    'path, is_safe',
    [
        pytest.param('', True, id='root path implicit'),
        pytest.param('.', True, id='root path explicit'),
        pytest.param('subfolder', True, id='subfolder implicit'),
        pytest.param('./subfolder', True, id='subfolder excplicit'),
        pytest.param('/unsafe/a', False, id='absolute path'),
        pytest.param('../unsafe/a', False, id='outside root start'),
        pytest.param('subfolder/../../unsafe', False, id='outside root middle'),
        pytest.param('safe/../safe', True, id='redundant traversal'),
        pytest.param(None, False, id='Not string'),
        pytest.param('safe//', False, id='Invalid 1'),
        pytest.param('safe\n', False, id='Invalid 2'),
    ],
)
def test_is_safe_relative_path(path, is_safe):
    assert is_safe_relative_path(path) == is_safe
