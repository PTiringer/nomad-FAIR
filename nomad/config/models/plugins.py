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

import importlib
import os
import shutil
import sys
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Literal, Union, cast

from pydantic import BaseModel, Field, model_validator

from nomad.common import download_file, get_package_path, is_safe_relative_path, is_url

from .common import Options
from .ui import App

example_prefix = '__examples__'

if TYPE_CHECKING:
    from fastapi import FastAPI

    from nomad.metainfo import SchemaPackage
    from nomad.normalizing import Normalizer as NormalizerBaseClass
    from nomad.parsing import Parser as ParserBaseClass


class EntryPoint(BaseModel):
    """Base model for a NOMAD plugin entry points."""

    id: str | None = Field(
        None,
        description='Unique identifier corresponding to the entry point name. Automatically set to the plugin entry point name in pyproject.toml.',
        hidden=True,
    )  # type: ignore[call-overload]
    entry_point_type: str = Field(
        description='Determines the entry point type.', hidden=True
    )  # type: ignore[call-overload]
    name: str | None = Field(None, description='Name of the plugin entry point.')
    description: str | None = Field(
        None, description='A human readable description of the plugin entry point.'
    )
    plugin_package: str | None = Field(
        None,
        description='The plugin package from which this entry points comes from.',
        hidden=True,
    )  # type: ignore[call-overload]

    def dict_safe(self):
        """Used to serialize the non-confidential parts of a plugin model. This
        function can be overridden in subclasses to expose more information.
        """
        return self.model_dump(
            include=EntryPoint.model_fields.keys(), exclude_none=True
        )


class AppEntryPoint(EntryPoint):
    """Base model for app plugin entry points."""

    entry_point_type: Literal['app'] = Field(
        'app', description='Determines the entry point type.', hidden=True
    )  # type: ignore[call-overload]
    app: App = Field(description='The app configuration.')

    def dict_safe(self):
        return self.model_dump(
            include=AppEntryPoint.model_fields.keys(), exclude_none=True
        )


class SchemaPackageEntryPoint(EntryPoint, metaclass=ABCMeta):
    """Base model for schema package plugin entry points."""

    entry_point_type: Literal['schema_package'] = Field(
        'schema_package', description='Specifies the entry point type.', hidden=True
    )  # type: ignore[call-overload]

    @abstractmethod
    def load(self) -> 'SchemaPackage':
        """Used to lazy-load a schema package instance. You should override this
        method in your subclass. Note that any Python module imports required
        for the schema package should be done within this function as well."""
        pass


class NormalizerEntryPoint(EntryPoint, metaclass=ABCMeta):
    """Base model for normalizer plugin entry points."""

    entry_point_type: Literal['normalizer'] = Field(
        'normalizer', description='Determines the entry point type.', hidden=True
    )  # type: ignore[call-overload]
    level: int = Field(
        0,
        description="""
        Integer that determines the execution order of this normalizer within
        the processing of an individual entry. Normalizers with the lowest level
        is run first.
        """,
    )

    @abstractmethod
    def load(self) -> 'NormalizerBaseClass':
        """Used to lazy-load a normalizer instance. You should override this
        method in your subclass. Note that any Python module imports required
        for the normalizer class should be done within this function as well."""
        pass


class ParserEntryPoint(EntryPoint, metaclass=ABCMeta):
    """Base model for parser plugin entry points."""

    entry_point_type: Literal['parser'] = Field(
        'parser', description='Determines the entry point type.', hidden=True
    )  # type: ignore[call-overload]
    level: int = Field(
        0,
        description="""
        Integer that determines the execution order of this parser within an
        upload. Parser with lowest level will be executed first. Note that this
        only controls the order in which matched parsers are executed, but does
        not affect the order in which parsers are matched to files.
    """,
    )
    aliases: list[str] = Field([], description="""List of alternative parser names.""")
    mainfile_contents_re: str | None = Field(
        None,
        description="""
        A regular expression that is applied the content of a potential mainfile.
        If this expression is given, the parser is only considered for a file, if the
        expression matches.
    """,
    )
    mainfile_name_re: str = Field(
        r'.*',
        description="""
        A regular expression that is applied the name of a potential mainfile.
        If this expression is given, the parser is only considered for a file, if the
        expression matches.
    """,
    )
    mainfile_mime_re: str = Field(
        r'.*',
        description="""
        A regular expression that is applied the mime type of a potential
        mainfile. If this expression is given, the parser is only considered
        for a file, if the expression matches.
    """,
    )
    mainfile_binary_header: bytes | None = Field(
        None,
        description="""
        Matches a binary file if the given bytes are included in the file.
    """,
    )
    mainfile_binary_header_re: bytes | None = Field(
        None,
        description="""
        Matches a binary file if the given binary regular expression bytes matches the
        file contents.
    """,
    )
    mainfile_alternative: bool = Field(
        False,
        description="""
        If True, the parser only matches a file, if no other file in the same directory
        matches a parser.
    """,
    )
    mainfile_contents_dict: dict | None = Field(
        None,
        description="""
        Is used to match structured data files like JSON or HDF5.
    """,
    )
    supported_compressions: list[str] = Field(
        [],
        description="""
        Files compressed with the given formats (e.g. xz, gz) are uncompressed and
        matched like normal files.
    """,
    )

    @abstractmethod
    def load(self) -> 'ParserBaseClass':
        """Used to lazy-load a parser instance. You should override this method
        in your subclass. Note that any Python module imports required for the
        parser class should be done within this function as well."""
        pass

    def dict_safe(self):
        # The binary data types are removed from the safe serialization: binary
        # data is not JSON serializable.
        keys = set(list(ParserEntryPoint.model_fields.keys()))
        keys.remove('mainfile_binary_header_re')
        keys.remove('mainfile_binary_header')

        return self.model_dump(include=keys, exclude_none=True)


class UploadResource(BaseModel):
    """Represents a request to include a certain resource into an example
    upload. Can point to a local folder/file, or alternatively to an online
    resource that can be downloaded.
    """

    path: str = Field(
        description="""
        Path to a file/folder within the python package (filepaths should start
        from the package root directory) or to an online URL.
        """
    )
    target: str = Field(
        '', description='File path within the upload where the file should be stored.'
    )


class ExampleUploadEntryPoint(EntryPoint):
    """Base model for example upload plugin entry points."""

    entry_point_type: Literal['example_upload'] = Field(
        'example_upload', description='Determines the entry point type.', hidden=True
    )  # type: ignore[call-overload]
    category: str | None = Field(description='Category for the example upload.')
    title: str | None = Field(description='Title of the example upload.')
    description: str | None = Field(
        description='Longer description of the example upload.'
    )
    resources: None | (
        # Note that the order here matters: pydantic may interpret a dictionary
        # as a list of strings instead of an UploadResource object if the order
        # is wrong here.
        list[UploadResource | str] | UploadResource | str
    ) = Field(None, description='List of data resources for this example upload.')
    path: str | None = Field(
        None,
        deprecated='"path" is deprecated, use "resources" instead.',
    )
    url: str | None = Field(
        None,
        deprecated='"url" is deprecated, use "resources" instead.',
    )
    from_examples_directory: bool = Field(
        False,
        description='Whether this example upload should be read from the "examples" directory.',
        hidden=True,
    )  # type: ignore[call-overload]

    def get_package_path(self):
        """Once all built-in example uploads have been removed, this function
        call can be replaced with `get_package_path(self.plugin_package)`.
        """
        return (
            os.path.abspath('examples/data')
            if self.from_examples_directory
            else get_package_path(self.plugin_package)
        )

    def resolve_resource(self, resource: UploadResource, upload_path: str):
        """Used to resolve an `UploadResource` by downloading/copying it's
        contents to the upload path.

        Args:
            resource: The resource to resolve.
            upload_path: The root folder for the upload where the data should be
                stored.
        """

        # Perform initial checks
        url = False
        copy_folder_contents = False
        source = resource.path
        target = resource.target
        if is_url(source):
            url = True
        else:
            content_suffix = '/*'
            if source.endswith(content_suffix):
                copy_folder_contents = True
                source = source[: -len(content_suffix)]

            # Check that only safe relative paths are given as target
            assert is_safe_relative_path(target), (
                f'Upload resource target "{resource.target}" in example upload "{self.id}" is targeting files outside the upload directory.'
            )

            # Check that only safe relative paths are given as source
            assert is_safe_relative_path(source), (
                f'Upload resource path "{resource.path}" in example upload "{self.id}" is targeting files outside the Python package directory.'
            )

            source = os.path.join(self.get_package_path(), source)

            # Validate that files/folders exist
            assert os.path.exists(source), (
                f'Upload resource path "{resource.path}" in example upload "{self.id}" could not be found.'
            )

        # Determine file target location and create missing folder structures.
        # If no target is given, the file/folder is copied as it is to the
        # upload root location. If the target points to an existing folder, the
        # file/folder is copied there. Otherwise a new file/folder is
        # constructed at the given target location, also creating any missing
        # folder structures. This behaviour is similar to the unix `cp` command
        # (with the addition of automatic folder creation).
        if resource.target:
            target = os.path.join(upload_path, target)
            if os.path.isdir(target):
                if not copy_folder_contents:
                    target = os.path.join(target, os.path.basename(source))
            else:
                os.makedirs(
                    target if copy_folder_contents else os.path.dirname(target),
                    exist_ok=True,
                )
        else:
            target = (
                upload_path
                if copy_folder_contents
                else os.path.join(upload_path, os.path.basename(source))
            )

        # Download online resources
        if url:
            download_file(source, target)
        # Copy file/folder from python package
        else:
            if os.path.isdir(source):
                if copy_folder_contents:
                    for item in os.listdir(source):
                        src_path = os.path.join(source, item)
                        dest_path = os.path.join(target, item)
                        if os.path.isdir(src_path):
                            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                        else:
                            shutil.copyfile(src_path, dest_path)
                else:
                    shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                shutil.copyfile(source, target)

    def load(self, upload_path: str):
        """Function for adding files/folders into the upload. Called when the
        example upload is instantiated.

        You may overload this method to customize the resource loading. Make use
        of the 'resolve_resource' function that can handle e.g. file downloading
        and file resolution within the Python package for you. When fetching or
        creating files with custom logic, remember to store the resulting files
        to the given `upload_path`.

        Args:
            upload_path: The filepath for the upload root folder. Any
                downloaded/created/copied files should be placed in this folder
                for them to end up correctly in the upload.
        """
        for resource in self.resources:
            self.resolve_resource(cast(UploadResource, resource), upload_path)

    def dict_safe(self):
        return self.dict(
            include=ExampleUploadEntryPoint.__fields__.keys(), exclude_none=True
        )

    @model_validator(mode='before')
    @classmethod
    def _validate(cls, values):
        # Normalize all different forms of input to a list of
        # ExampleUploadResource objects.
        if isinstance(values, BaseModel):
            values = values.model_dump(exclude_none=True)
        resources = values.get('resources', None)
        resource_objects = []
        if resources:
            if not isinstance(resources, list):
                resources = [resources]
            for resource in resources:
                if isinstance(resource, str):
                    resource = {'path': resource}
                elif isinstance(resource, UploadResource):
                    resource = resource.dict()
                resource_objects.append(resource)

        # Backwards compatibility for path and url
        else:
            path = values.get('path')
            url = values.get('url')
            if path:
                resource_objects.append({'path': path})
            if url:
                resource_objects.append({'path': url})

        values['resources'] = resource_objects

        return values


class APIEntryPoint(EntryPoint, metaclass=ABCMeta):
    """Base model for API plugin entry points."""

    entry_point_type: Literal['api'] = Field(
        'api', description='Specifies the entry point type.', hidden=True
    )  # type: ignore[call-overload]

    prefix: str = Field(
        None,
        description=(
            'The prefix for the API. The URL for the API will be the base URL of the NOMAD '
            'installation followed by this prefix. The prefix must not collide with any other '
            'API prefixes. There is no default, this field must be set.'
        ),
    )

    @model_validator(mode='before')
    @classmethod
    def prefix_must_be_defined_and_valid(cls, v):
        import urllib.parse

        if 'prefix' not in v:
            raise ValueError('prefix must be defined')
        if not v['prefix']:
            raise ValueError('prefix must be defined')
        if urllib.parse.quote(v['prefix']) != v['prefix']:
            raise ValueError('prefix must be a valid URL path')

        v['prefix'] = v['prefix'].strip('/')
        return v

    @abstractmethod
    def load(self) -> 'FastAPI':
        """Used to lazy-load the API instance. You should override this
        method in your subclass. Note that any Python module imports required
        for the API should be done within this function as well."""
        pass


class PluginBase(BaseModel):
    """
    Base model for a NOMAD plugin.

    This should not be used. Plugins should instantiate concrete Plugin models like
    Parser or Schema.
    """

    plugin_type: str = Field(
        description='The type of the plugin.',
    )
    id: str | None = Field(None, description='The unique identifier for this plugin.')
    name: str = Field(
        description='A short descriptive human readable name for the plugin.'
    )
    description: str | None = Field(
        None, description='A human readable description of the plugin.'
    )
    plugin_documentation_url: str | None = Field(
        None, description='The URL to the plugins main documentation page.'
    )
    plugin_source_code_url: str | None = Field(
        None, description='The URL of the plugins main source code repository.'
    )

    def dict_safe(self):
        """Used to serialize the non-confidential parts of a plugin model. This
        function can be overridden in subclasses to expose more information.
        """
        return self.model_dump(
            include=PluginBase.model_fields.keys(), exclude_none=True
        )


class PythonPluginBase(PluginBase):
    """
    A base model for NOMAD plugins that are implemented in Python.
    """

    python_package: str = Field(
        description="""
        Name of the python package that contains the plugin code and a
        plugin metadata file called `nomad_plugin.yaml`.
    """
    )

    def import_python_package(self):
        if not self.python_package:
            raise ValueError('Python plugins must provide a python_package.')
        importlib.import_module(self.python_package)


class Schema(PythonPluginBase):
    """
    A Schema describes a NOMAD Python schema that can be loaded as a plugin.
    """

    package_path: str | None = Field(
        None,
        description='Path of the plugin package. Will be determined using python_package if not explicitly defined.',
    )
    key: str | None = Field(None, description='Key used to identify this plugin.')
    plugin_type: Literal['schema'] = Field(
        'schema',
        description="""
        The type of the plugin. This has to be the string `schema` for schema plugins.
    """,
    )


class Normalizer(PythonPluginBase):
    """
    A Normalizer describes a NOMAD normalizer that can be loaded as a plugin.
    """

    normalizer_class_name: str = Field(
        description="""
        The fully qualified name of the Python class that implements the normalizer.
        This class must have a function `def normalize(self, logger)`.
    """
    )
    plugin_type: Literal['normalizer'] = Field(
        'normalizer',
        description="""
        The type of the plugin. This has to be the string `normalizer` for normalizer plugins.
    """,
    )


class Parser(PythonPluginBase):
    """
    A Parser describes a NOMAD parser that can be loaded as a plugin.

    The parser itself is referenced via `python_name`. For Parser instances `python_name`
    must refer to a Python class that has a `parse` function. The other properties are
    used to create a `MatchingParserInterface`. This comprises general metadata that
    allows users to understand what the parser is, and metadata used to decide if a
    given file "matches" the parser.
    """

    # TODO the nomad_plugin.yaml for each parser needs some cleanup. The way parser metadata
    #      is presented in the UIs should be rewritten
    # TODO ideally we can somehow load parser plugin models lazily. Right now importing
    #      config will open all `nomad_plugin.yaml` files. But at least there is no python import
    #      happening.
    # TODO this should fully replace MatchingParserInterface
    # TODO most actual parser do not implement any abstract class. The Parser class has an
    #      abstract is_mainfile, which does not allow to separate parser implementation and plugin
    #      definition.

    plugin_type: Literal['parser'] = Field(
        'parser',
        description="""
        The type of the plugin. This has to be the string `parser` for parser plugins.
        """,
    )
    parser_class_name: str = Field(
        description="""
        The fully qualified name of the Python class that implements the parser.
        This class must have a function `def parse(self, mainfile, archive, logger)`.
        """
    )
    parser_as_interface: bool = Field(
        False,
        description="""
        By default the parser metadata from this config (and the loaded nomad_plugin.yaml)
        is used to instantiate a parser interface that is lazy loading the actual parser
        and performs the mainfile matching. If the parser interface matching
        based on parser metadata is not sufficient and you implemented your own
        is_mainfile parser method, this setting can be used to use the given
        parser class directly for parsing and matching.
        """,
    )
    mainfile_contents_re: str | None = Field(
        None,
        description="""
        A regular expression that is applied the content of a potential mainfile.
        If this expression is given, the parser is only considered for a file, if the
        expression matches.
        """,
    )
    mainfile_name_re: str = Field(
        r'.*',
        description="""
        A regular expression that is applied the name of a potential mainfile.
        If this expression is given, the parser is only considered for a file, if the
        expression matches.
        """,
    )
    mainfile_mime_re: str = Field(
        r'text/.*',
        description="""
        A regular expression that is applied the mime type of a potential mainfile.
        If this expression is given, the parser is only considered for a file, if the
        expression matches.
        """,
    )
    mainfile_binary_header: bytes | None = Field(
        None,
        description="""
        Matches a binary file if the given bytes are included in the file.
        """,
    )
    mainfile_binary_header_re: bytes | None = Field(
        None,
        description="""
        Matches a binary file if the given binary regular expression bytes matches the
        file contents.
        """,
    )
    mainfile_alternative: bool = Field(
        False,
        description="""
        If True, the parser only matches a file, if no other file in the same directory
        matches a parser.
        """,
    )
    mainfile_contents_dict: dict | None = Field(
        None,
        description="""
        Is used to match structured data files like JSON, HDF5 or csv/excel files. In case of a csv/excel file
        for example, in order to check if certain columns exist in a given sheet, one can set this attribute to
        `'__has_all_keys': [<column names>]`. In case the csv/excel file contains comments that
        are supposed to be ignored, use this reserved key-value pair
        `'__has_comment': '<symbol>'` at the top level of the dictionary. Also in order to check if a certain
        sheet name with specific column names exist, one may set this attribute to:
        {'<sheet name>': {'__has_all_keys': [<column names>]}}.
        Available options are:
        <i>__has_key: str<i>
        <i>__has_all_keys: List[str]<i>
        <i>__has_only_keys: List[str]<i>
        <i>__has_comment: str<i> (only for csv/xlsx files)
        """,
    )
    supported_compressions: list[str] = Field(
        [],
        description="""
        Files compressed with the given formats (e.g. xz, gz) are uncompressed and
        matched like normal files.
        """,
    )
    domain: str = Field(
        'dft',
        description="""
        The domain value `dft` will apply all normalizers for atomistic codes. Deprecated.
        """,
    )
    level: int = Field(
        0,
        description="""
        The order by which the parser is executed with respect to other parsers.
        """,
    )
    code_name: str | None = None
    code_homepage: str | None = None
    code_category: str | None = None
    metadata: dict | None = Field(
        None,
        description="""
        Metadata passed to the UI. Deprecated.""",
    )

    def create_matching_parser_interface(self):
        if self.parser_as_interface:
            from nomad.parsing.parser import import_class

            Parser = import_class(self.parser_class_name)
            return Parser()

        from nomad.parsing.parser import MatchingParserInterface

        data = self.model_dump()
        del data['id']
        del data['description']
        del data['python_package']
        del data['plugin_type']
        del data['parser_as_interface']
        del data['plugin_source_code_url']
        del data['plugin_documentation_url']

        return MatchingParserInterface(**data)


EntryPointType = Union[  # noqa
    Schema,
    Normalizer,
    Parser,
    SchemaPackageEntryPoint,
    ParserEntryPoint,
    NormalizerEntryPoint,
    AppEntryPoint,
    ExampleUploadEntryPoint,
    APIEntryPoint,
]


class EntryPoints(Options):
    options: dict[str, EntryPointType] = Field(
        dict(), description='The available plugin entry points.'
    )


class PluginPackage(BaseModel):
    name: str = Field(
        description='Name of the plugin Python package, read from pyproject.toml.'
    )
    description: str | None = Field(
        None, description='Package description, read from pyproject.toml.'
    )
    version: str | None = Field(
        None, description='Plugin package version, read from pyproject.toml.'
    )
    homepage: str | None = Field(
        None,
        description='Link to the plugin package homepage, read from pyproject.toml.',
    )
    documentation: str | None = Field(
        None,
        description='Link to the plugin package documentation page, read from pyproject.toml.',
    )
    repository: str | None = Field(
        None,
        description='Link to the plugin package source code repository, read from pyproject.toml.',
    )
    entry_points: list[str] = Field(
        description='List of entry point ids contained in this package, read form pyproject.toml'
    )


class Plugins(BaseModel):
    entry_points: EntryPoints = Field(
        description='Used to control plugin entry points.'
    )
    plugin_packages: dict[str, PluginPackage] = Field(
        description="""
        Contains the installed installed plugin packages with the package name
        used as a key. This is autogenerated and should not be modified.
        """
    )


def add_plugin(plugin: Schema) -> None:
    """Function for dynamically adding a plugin."""
    from nomad.config import config
    from nomad.metainfo.elasticsearch_extension import entry_type

    if plugin.package_path not in sys.path:
        sys.path.insert(0, plugin.package_path)

    # Add plugin to config
    config.plugins.entry_points.options[plugin.key] = plugin

    # Add plugin to Package registry
    package = importlib.import_module(plugin.python_package)
    package.m_package.__init_metainfo__()

    # Reload the dynamic quantities so that API is aware of the plugin
    # quantities.
    entry_type.reload_quantities_dynamic()


def remove_plugin(plugin) -> None:
    """Function for removing a plugin."""
    from nomad.config import config
    from nomad.metainfo import Package
    from nomad.metainfo.elasticsearch_extension import entry_type

    # Remove from path
    try:
        sys.path.remove(plugin.package_path)
    except Exception:
        pass

    # Remove package as plugin
    del config.plugins.entry_points.options[plugin.key]

    # Remove plugin from Package registry
    package = importlib.import_module(plugin.python_package).m_package
    for key, i_package in Package.registry.items():
        if i_package is package:
            del Package.registry[key]
            break

    # Reload the dynamic quantities so that API is aware of the plugin
    # quantities.
    entry_type.reload_quantities_dynamic()
