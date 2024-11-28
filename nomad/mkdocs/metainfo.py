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

import yaml
import json
from enum import Enum
from pydantic import BaseModel
from pydantic.fields import ModelField
import os.path
from typing import List, Set, Tuple, Any, Optional, Dict
from typing_extensions import Literal, _AnnotatedAlias  # type: ignore
from inspect import isclass
from markdown.extensions.toc import slugify

from nomad.utils import strip
from nomad.config import config
from nomad.config.models.plugins import Parser, EntryPointType
from nomad.app.v1.models import query_documentation, owner_documentation
from nomad.app.v1.routers.entries import archive_required_documentation
from nomad import utils
from nomad.metainfo import Property, Quantity, Datatype, Reference, SubSection
from nomad.datamodel.data import ArchiveSection


def get_reference(section_def, pkg) -> str:
    if section_def.m_parent == pkg:
        return f'[`{section_def.name}`](#{section_def.name.lower()})'

    return f'`{section_def.qualified_name()}`'


def get_property_type_info(property: Property, pkg=None) -> str:
    if isinstance(property, Quantity):
        type = property.type
        if isinstance(type, Reference):
            return get_reference(type.target_section_def, pkg)
        if isinstance(type, Datatype):
            try:
                return f'`{type.serialize_self()["type_data"]}`'
            except NotImplementedError:
                pass

    if isinstance(property, SubSection):
        return get_reference(property.section_def, pkg)

    return '*unknown type*'


def get_property_description(property: Property) -> Optional[str]:
    value = property.description
    if value:
        value = utils.strip(value)
        value = value.replace('\n\n', '<br/>').replace('\n', ' ')

    return value


def get_quantity_default(quantity: Quantity) -> str:
    default = quantity.default
    if isinstance(default, dict):
        return 'Complex object, default value not displayed.'
    return f'`{str(quantity.default)}`' if quantity.default is not None else ''


def get_property_options(property: Property) -> str:
    options: List[str] = []
    if isinstance(property, Quantity):
        if property.shape != []:
            options.append(f'**shape**=`{property.shape}`')
        if property.unit:
            options.append(f'**unit**=`{property.unit}`')

        default = get_quantity_default(property)
        if default != '':
            options.append(f'**default**=`{default}`')

    if isinstance(property, SubSection):
        options.append('**sub-section**')
        if property.repeats:
            options.append('**repeats**')

    return ', '.join(options)


def section_markdown_from_section_cls(
    section_cls, name=None, heading=None, hide=[], pkg=None
):
    section_def = section_cls.m_def
    properties = section_def.quantities + section_def.sub_sections

    if not name:
        name = section_cls.__name__

    def content(property):
        result = []
        description = get_property_description(property)
        if description:
            result.append(description)
        options = get_property_options(property)
        if options != '':
            result.append(options)

        return '</br>'.join(result)

    def property_row(property):
        if property.name.startswith('m_'):
            return ''
        type_name = get_property_type_info(property, pkg)
        return f'|{property.name}|{type_name}|{content(property)}|\n'

    if heading is None:
        result = f'### {name}\n'
    else:
        result = heading + '\n'

    if section_def.description and section_def.description != '':
        result += f'**description**: {utils.strip(section_def.description)}\n\n'

    if len(section_def.base_sections) > 0:
        base_sections = [
            get_reference(base_section, pkg)
            for base_section in section_def.base_sections
        ]
        result += f'**inherits from**: {", ".join(base_sections)}\n\n'

    if section_def.links:
        links = [f'[{link}]({link})' for link in section_def.links]
        result += f'**links**: {", ".join(links)}\n\n'

    if len(properties) > 0:
        result += '**properties**:\n\n'
        result += '|name|type| |\n'
        result += '|----|----|-|\n'
        result += ''.join(
            [
                property_row(property)
                for property in properties
                if property.name not in hide
            ]
        )
        result += '\n\n'

    if section_cls.normalize and section_cls.normalize.__doc__ != ArchiveSection.normalize.__doc__:
        if section_cls.normalize.__doc__:
            result += (
                f'**normalization**: {utils.strip(section_cls.normalize.__doc__)}\n\n'
            )
        else:
            result += f'**normalization** without further documentation\n\n'

    return result


def package_markdown_from_package(pkg):
    return ''.join(
        [
            section_markdown_from_section_cls(section_def.section_cls, pkg=pkg)
            for section_def in pkg.section_definitions
        ]
    )
