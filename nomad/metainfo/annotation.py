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

from __future__ import annotations

from typing import Any, ClassVar, ForwardRef

from pydantic import BaseModel, ConfigDict, Field


class Annotation:
    """Base class for annotations."""

    def m_to_dict(self):
        """
        Returns a JSON serializable representation that is used for exporting the
        annotation to JSON.
        """
        return str(self.__class__.__name__)


class DefinitionAnnotation(Annotation):
    """Base class for annotations for definitions."""

    def __init__(self):
        self.definition = None

    def init_annotation(self, definition):
        self.definition = definition


class SectionAnnotation(DefinitionAnnotation):
    """
    Special annotation class for section definition that allows to auto add annotations
    to section instances.
    """

    def new(self, section) -> dict[str, Any]:
        return {}


Definition = ForwardRef('Definition')


class AnnotationModel(Annotation, BaseModel):
    """
    Base class for defining annotation models. Annotations used with simple dict-based
    values, can be validated by defining and registering a formal pydantic-based
    model.
    """

    m_definition: Definition = Field(  # type: ignore
        None,
        description='The definition that this annotation is annotating.',
        exclude=True,
    )

    m_error: str = Field(
        None, description='Holds a potential validation error.', exclude=True
    )

    m_registry: ClassVar[dict[str, type[AnnotationModel]]] = {}
    """ A static member that holds all currently known annotations with pydantic model. """

    def m_to_dict(self, *args, **kwargs):
        return self.model_dump(exclude_unset=True)

    model_config = ConfigDict(
        extra='allow',
        validate_assignment=True,
        arbitrary_types_allowed=True,
        use_enum_values=True,
    )
