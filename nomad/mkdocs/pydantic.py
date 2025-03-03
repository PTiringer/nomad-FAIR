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
Definitions that are used in the documentation via mkdocs-macro-plugin.
"""

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


exported_config_models = set()  # type: ignore


def get_field_type_info(field: ModelField) -> Tuple[str, Set[Any]]:
    """Used to recursively walk through a type definition, building up a cleaned
    up type name and returning all of the classes that were used.

    Args:
        type_: The type to inspect. Can be any valid type definition.

    Returns:
        Tuple containing the cleaned up type name and a set of classes
        found inside.
    """
    # Notice that pydantic does not store the full type in field.type_, but instead in
    # field.outer_type_
    type_ = field.outer_type_
    type_name: List[str] = []
    models = set()

    def fetch_models(type_, type_name):
        """Used to recursively walk through a type definition, building up a
        pretty type name and adding any found models to the docs.
        """
        # Get the type name
        early_stop = False
        skip_parent = False
        cls = type_
        name = None

        # All string subclasses displayed as str
        if isclass(type_) and issubclass(type_, str):
            name = 'str'
        elif isclass(type_) and issubclass(type_, int):
            name = 'int'
        # Special handling for type definitions
        elif hasattr(type_, '__origin__'):
            origin = type_.__origin__
            # For literals we report the actual data type that is stored inside.
            if origin == Literal:
                arg = type_.__args__[0]
                cls = type(arg)
                early_stop = True
            # Skip the annotated container. In newer python versions the
            # identification of 'Annotated' could be done with
            # `get_origin(a) is Annotated``, but this is the cleanest
            # solution with Python 3.7.
            elif type(cls) is _AnnotatedAlias:
                skip_parent = True
            else:
                name = str(cls).split('[', 1)[0].rsplit('.')[-1]

        if not skip_parent:
            if not name:
                try:
                    name = cls.__name__
                except Exception:
                    name = str(cls)
            type_name.append(name)
            if hasattr(type_, '__origin__'):
                models.add(type_.__origin__)
            else:
                models.add(type_)

        if not early_stop:
            if hasattr(type_, '__args__'):
                if not skip_parent:
                    type_name.append('[')
                origin = type_.__origin__
                for iarg, arg in enumerate(type_.__args__):
                    fetch_models(arg, type_name)
                    if iarg + 1 != len(type_.__args__):
                        type_name.append(', ')
                if not skip_parent:
                    type_name.append(']')

    fetch_models(type_, type_name)

    return ''.join(type_name), models


def get_field_description(field: ModelField) -> Optional[str]:
    """Retrieves the description for a pydantic field as a markdown string.

    Args:
        field: The pydantic field to inspect.

    Returns:
        Markdown string for the description.
    """
    value = field.field_info.description
    if value:
        value = utils.strip(value)
        value = value.replace('\n\n', '<br/>').replace('\n', ' ')

    return value


def get_field_default(field: ModelField) -> Optional[str]:
    """Retrieves the default value from a pydantic field as a markdown string.

    Args:
        field: The pydantic field to inspect.

    Returns:
        Markdown string for the default value.
    """
    default_value = field.default
    if default_value is not None:
        if isinstance(default_value, (dict, BaseModel)):
            default_value = 'Complex object, default value not displayed.'
        elif default_value == '':
            default_value = '""'
        else:
            default_value = f'`{default_value}`'
    return default_value


def get_field_options(field: ModelField) -> Dict[str, Optional[str]]:
    """Retrieves a dictionary of value-description pairs from a pydantic field.

    Args:
        field: The pydantic field to inspect.

    Returns:
        Dictionary containing the possible options and their description for
        this field. The description may be None indicating that it does not exist.
    """
    options: Dict[str, Optional[str]] = {}
    if isclass(field.type_) and issubclass(field.type_, Enum):
        for x in field.type_:
            options[str(x.value)] = None
    return options


def get_field_deprecated(field: ModelField) -> bool:
    """Returns whether the given pydantic field is deprecated or not.

    Args:
        field: The pydantic field to inspect.

    Returns:
        Whether the field is deprecated.
    """
    return field.field_info.extra.get('deprecated', False)


def pydantic_model_from_model(model, name=None, heading=None, hide=[]):
    fields = model.__fields__
    required_models = set()
    if not name:
        exported_config_models.add(model.__name__)
        name = model.__name__

    exported_config_models.add(name)

    def content(field):
        result = []
        description = get_field_description(field)
        if description:
            result.append(description)
        default = get_field_default(field)
        if default:
            result.append(f'*default:* {default}')
        options = get_field_options(field)
        if options:
            option_list = '*options:*<br/>'
            for name, desc in options.items():
                option_list += f' - `{name}{f": {desc}" if desc else ""}`<br/>'
            result.append(option_list)
        if get_field_deprecated(field):
            result.append('**deprecated**')

        return '</br>'.join(result)

    def field_row(field):
        if field.name.startswith('m_'):
            return ''
        type_name, classes = get_field_type_info(field)
        nonlocal required_models
        required_models |= {
            cls for cls in classes if isclass(cls) and issubclass(cls, BaseModel)
        }
        return f'|{field.name}|`{type_name}`|{content(field)}|\n'

    if heading is None:
        result = f'### {name}\n'
    else:
        result = heading + '\n'

    if model.__doc__ and model.__doc__ != '':
        result += utils.strip(model.__doc__) + '\n\n'

    result += '|name|type| |\n'
    result += '|----|----|-|\n'
    result += ''.join(
        [field_row(field) for field in fields.values() if field.name not in hide]
    )

    for required_model in required_models:
        if required_model.__name__ not in exported_config_models:
            result += '\n\n'
            result += pydantic_model_from_model(required_model)

    return result


def pydantic_model(path, heading=None, hide=[]):  # pylint: disable=unused-variable
    """
    Produces markdown code for the given pydantic model.

    Arguments:
        path: The python qualified name of the model class.
    """
    import importlib

    module_name, name = path.rsplit('.', 1)
    module = importlib.import_module(module_name)
    model = getattr(module, name)

    return pydantic_model_from_model(model, heading=heading, hide=hide)
