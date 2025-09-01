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

"""
API endpoint that deliver backend configuration details.
"""

import re
from datetime import timedelta
from enum import Enum
from typing import Final

from fastapi.routing import APIRouter
from pydantic.fields import Field
from pydantic.main import BaseModel

from nomad import normalizing
from nomad.app.v1.models import Aggregation, StatisticsAggregation
from nomad.config import config
from nomad.mongo.cache import cache
from nomad.parsing import parsers
from nomad.parsing.parsers import code_metadata
from nomad.search import search
from nomad.utils import strip

INFO_CACHE_KEY: Final[str] = 'info'
INFO_CACHE_TTL: Final[timedelta] = timedelta(days=1)

router = APIRouter()


class APITag(str, Enum):
    DEFAULT = 'info'


class MetainfoModel(BaseModel):
    all_package: str | None = Field(
        None,
        description=strip(
            """
        Name of the metainfo package that references all available packages, i.e.
        the complete metainfo."""
        ),
    )

    root_section: str | None = Field(
        None,
        description=strip(
            """
        Name of the topmost section, e.g. section run for computational material science
        data."""
        ),
    )


class StatisticsModel(BaseModel):
    n_entries: int | None = Field(None, description='Number of entries in NOMAD')
    n_uploads: int | None = Field(None, description='Number of uploads in NOMAD')
    n_quantities: int | None = Field(
        None,
        description='Accumulated number of quantities over all entries in the Archive',
    )
    n_calculations: int | None = Field(
        None,
        description='Accumulated number of calculations, e.g. total energy calculations in the Archive',
    )
    n_materials: int | None = Field(None, description='Number of materials in NOMAD')


class CodeInfoModel(BaseModel):
    code_name: str | None = Field(None, description='Name of the code or input format')
    code_homepage: str | None = Field(
        None, description='Homepage of the code or input format'
    )


class InfoModel(BaseModel):
    parsers: list[str]
    metainfo_packages: list[str]
    codes: list[CodeInfoModel]
    normalizers: list[str]
    plugin_entry_points: list[dict] | None = Field(
        None,
        description='List of plugin entry points that are activated in this deployment.',
    )
    plugin_packages: list[dict] | None = Field(
        None,
        description='List of plugin packages that are installed in this deployment.',
    )
    statistics: StatisticsModel | None = Field(
        None, description='General NOMAD statistics'
    )
    search_quantities: dict | None = Field(None, deprecated=True)
    version: str
    deployment: str
    oasis: bool
    # TODO this should be removed in later releases, once most regular NOMAD users
    # should have switched to a new GUI version.
    git: dict | None = Field(
        None,
        description=strip(
            """
        A deprecated field that always contains an empty value to retain some compatibility
        with older GUIs.
    """
        ),
    )


def get_statistics():
    search_response = search(
        aggregations=dict(
            statistics=Aggregation(
                statistics=StatisticsAggregation(
                    metrics=[
                        'n_entries',
                        'n_materials',
                        'n_uploads',
                        'n_quantities',
                        'n_calculations',
                    ]
                )
            )
        )
    )
    statistics = search_response.aggregations['statistics'].statistics.data
    return statistics


@router.get(
    '',
    tags=[APITag.DEFAULT],
    summary='Get information about the nomad backend and its configuration',
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
    response_model=InfoModel,
)
@cache(key=INFO_CACHE_KEY, ttl=INFO_CACHE_TTL)
async def get_info():
    """Return information about the nomad backend and its configuration."""

    parser_names = sorted(
        [re.sub(r'^(parsers?|missing)/', '', key) for key in parsers.parser_dict.keys()]
    )

    config.load_plugins()

    return {
        'parsers': parser_names,
        'metainfo_packages': [
            'general',
            'general.experimental',
            'common',
            'public',
        ]
        + parser_names,
        'codes': [
            {
                'code_name': x.get('codeLabel', 'unknown code'),
                'code_homepage': x.get('codeUrl'),
            }
            for x in sorted(
                code_metadata.values(),
                key=lambda info: info.get('codeLabel', 'unknown code').lower(),
            )
        ],
        'normalizers': [normalizer.__name__ for normalizer in normalizing.normalizers],
        'plugin_entry_points': [
            entry_point.dict_safe()
            for entry_point in config.plugins.entry_points.filtered_values()
        ]
        if config.plugins and config.plugins.entry_points
        else [],
        'plugin_packages': [
            plugin_package.model_dump()
            for plugin_package in config.plugins.plugin_packages.values()
        ]
        if config.plugins and config.plugins.plugin_packages
        else [],
        'statistics': get_statistics(),
        'version': config.meta.version,
        'deployment': config.meta.deployment,
        'oasis': config.oasis.is_oasis,
        'git': {},
    }
