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

from nomad.auth.scopes import Scope, _resolve_scopes


class TestResolveScopes:
    def test_no_wildcard(self):
        scopes = {'uploads:read', 'datasets:write', 'info:read'}
        assert _resolve_scopes(scopes) == scopes

        # test whitespace handling
        scopes = ['  uploads:read  ', '', '   ', '\n', 'info:read\t']
        assert _resolve_scopes(scopes) == {'uploads:read', 'info:read'}

    @pytest.mark.parametrize(
        'scope', ['uploads:unknown_action', 'unknown_resource:read']
    )
    def test_unknown_scope(self, scope):
        with pytest.raises(ValueError, match='Unknown concrete scopes'):
            _resolve_scopes({scope})

    @pytest.mark.parametrize('scope', ['uploads', 'uploads:read:extra', '*:*:*', '*'])
    def test_illegal_format(self, scope):
        with pytest.raises(ValueError, match=f'Illegal scope {scope}'):
            _resolve_scopes({scope})

    @pytest.mark.parametrize(
        'scope', ['up*:read', '*load:read', 'uploads:r*', 'uploads:*d']
    )
    def test_reject_partial_wildcard(self, scope):
        with pytest.raises(ValueError, match='Partial wildcard'):
            _resolve_scopes({scope})

    def test_wildcard(self):
        assert _resolve_scopes({'*:*'}) == Scope.all_values()

        resolved = _resolve_scopes({'uploads:*'})
        expected = {s for s in Scope.all_values() if s.startswith('uploads:')}
        assert resolved == expected
        assert resolved

        resolved = _resolve_scopes({'*:read'})
        expected = {s for s in Scope.all_values() if s.endswith(':read')}
        assert resolved == expected
        assert resolved

    def test_wildcards_deduplicate(self):
        resolved = _resolve_scopes({'uploads:*', 'uploads:read', '*:read'})
        expected = {s for s in Scope.all_values() if s.startswith('uploads:')} | {
            s for s in Scope.all_values() if s.endswith(':read')
        }
        assert resolved == expected

    @pytest.mark.parametrize('scope', ['not_a_resource:*', '*:not_an_action'])
    def test_unmatched_wildcard(self, scope):
        with pytest.raises(ValueError, match='Wildcards matched nothing'):
            _resolve_scopes({scope})
