import json
import os
import re
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any, Optional

import h5py
import jmespath
import jmespath.visitor
import numpy as np
from jsonpath_ng.parser import JsonPathParser
from lxml import etree
from pydantic import BaseModel, Field, model_validator

from nomad.datamodel import EntryArchive
from nomad.datamodel.metainfo.annotations import Mapper as MapperAnnotation
from nomad.metainfo import MSection, SubSection
from nomad.parsing.file_parser import TextParser as TextFileParser
from nomad.parsing.parser import ArchiveParser
from nomad.units import ureg
from nomad.utils import get_logger

MAPPING_ANNOTATION_KEY = 'mapping'


class JmespathOptions(jmespath.visitor.Options):
    def __init__(self, **kwargs):
        self.pop = False
        self.search = True

        for key in list(kwargs.keys()):
            if not hasattr(super(), key):
                setattr(self, key, kwargs[key])
                del kwargs[key]
        super().__init__(**kwargs)


LOGGER = get_logger(__name__)


class TreeInterpreter(jmespath.visitor.TreeInterpreter):
    def __init__(self, options=None):
        self.stack = []
        self._current_node = None
        self.current_stack = None
        self._parent = None
        self.nodes = []
        self.indices = []
        self.keys = []
        self._cache = []
        self._parent_key = '__parent'
        super().__init__(options)

    def visit(self, node, *args, **kwargs):
        node_type = node.get('type')
        for child in node.get('children'):
            if hasattr(child, 'get'):
                child[self._parent_key] = node_type

        value = super().visit(node, *args, **kwargs)
        node.pop(self._parent_key, None)
        return value

    def visit_field(self, node, value):
        parent = node.get(self._parent_key, None)
        if isinstance(value, list):
            if not value and not self._options.search:
                value.append({})
            if not value:
                return None
            value = value[-1]
        if not hasattr(value, 'get'):
            return None

        if not self._options.search:
            if parent == 'index_expression' and not isinstance(
                value.get(node['value']), list
            ):
                value[node['value']] = []

            value.setdefault(node['value'], [] if parent == 'index_expression' else {})

        if self.stack and not self.indices[-1]:
            parent_stack = self.stack[-1].get(self.keys[-1], {})
            if value == parent_stack or (
                isinstance(parent_stack, list) and value in parent_stack
            ):
                self.indices[-1] = [0]

        if parent != 'comparator':
            self.indices.append([])
            self.stack.append(value)
            self.keys.append(node['value'])

        try:
            return value.get(node['value'])
        except AttributeError:
            return None

    def visit_index_expression(self, node, value):
        value = super().visit_index_expression(node, value)
        if node.get(self._parent_key) == 'pipe' and self.indices:
            self.indices[-1] = []
        return value

    def visit_index(self, node, value):
        if not isinstance(value, list):
            return None

        index = node['value']
        n_value = len(value)
        if self._options.search and index >= n_value:
            return None

        n_target = abs(index) - n_value + (0 if index < 0 else 1)
        value.extend([{} for _ in range(n_target)])

        if self.indices:
            self.indices[-1] = [index]
        return value[index]

    def visit_slice(self, node, value):
        if not isinstance(value, list):
            return None

        s = slice(*node['children'])
        n_value = len(value)
        indices = list(range(s.start or 0, s.stop or n_value or 1, s.step or 1))
        if indices:
            max_index = max(np.abs(indices))
            min_index = min(indices)
            n_target = (
                max_index
                - n_value
                + (0 if min_index < 0 and max_index == -min_index else 1)
            )

            if max_index >= n_value and self._options.search:
                return None

            value.extend([{} for _ in range(n_target)])
        # if isinstance(value, h5py.Group):
        #     return [g for g in value.values()][s]
        self.indices[-1] = indices
        return value[s]


class ParsedResult(jmespath.parser.ParsedResult):
    def _set_value(self, value, options, data):
        self._interpreter = TreeInterpreter(options=options)
        result = self._interpreter.visit(self.parsed, value)

        values = []
        if not options.pop and data is None:
            return result, values

        stack, stack_indices, stack_keys = [], [], []
        for n, s in enumerate(self._interpreter.stack):
            add = s == self._interpreter.stack[-1]
            if not add:
                val = s[self._interpreter.keys[n]]
                add = val and not hasattr(
                    val[0] if isinstance(val, list) else val, 'get'
                )
            if add:
                stack.append(s)
                stack_indices.append(self._interpreter.indices[n])
                stack_keys.append(self._interpreter.keys[n])

        for n, indices in enumerate(stack_indices):
            d = (
                data[n]
                if isinstance(data, list)
                and len(data) > 1
                and len(data) == len(stack_indices)
                else data
            )
            if not indices:
                stack[n][stack_keys[n]] = d
                v = (
                    stack[n][stack_keys[n]]
                    if not options.pop
                    else stack[n].pop(stack_keys[n])
                )
                values.append(v)
                continue
            map_data = isinstance(d, list) and len(d) == len(indices)
            for nd in range(len(indices) - 1, -1, -1):
                index = indices[nd]
                stack[n][stack_keys[n]][index] = d[nd] if map_data else d
                v = (
                    stack[n][stack_keys[n]][index]
                    if not options.pop
                    else stack[n][stack_keys[n]].pop(index)
                )
                values.append(v)

        return result, values[0] if len(values) == 1 else values

    def search(self, value, **kwargs):
        options = JmespathOptions(search=True, **kwargs)
        return self._set_value(value, options, None)[0]

    def set(self, value, data, **kwargs):
        options = JmespathOptions(search=False, **kwargs)
        return self._set_value(value, options, data)[1]


class JmespathParser(jmespath.parser.Parser):
    """
    JmespathParser extension implementing search with pop and set functionalities.
    """

    def parse(self, expression):
        parsed_result = super().parse(expression)
        return ParsedResult(parsed_result.expression, parsed_result.parsed)


class PathParser(BaseModel):
    parser_name: str = Field(
        'jmespath', description="""Name of the parser to perform parsing."""
    )

    def get_data(self, path, source, **kwargs) -> Any:
        if self.parser_name == 'jmespath':

            def _get(path, source, **kwargs):
                return JmespathParser().parse(path).search(source, **kwargs)

            return _get(path, source, **kwargs)
        elif self.parser_name == 'jsonpath_ng':

            def _get(path, source, **kwargs):
                parser = JsonPathParser().parse(path)
                results = [match.value for match in parser.find(source)]
                if kwargs.get('pop'):
                    # TODO is find and filter somehow can be performed simulatenously
                    parser.filter(lambda v: True, source)
                return results[0] if len(results) == 1 else results

            return _get(path, source, **kwargs)

        return None

    def set_data(self, path, target, data, **kwargs) -> Any:
        if self.parser_name == 'jmespath':

            def _set(path, target, data, **kwargs):
                return JmespathParser().parse(path).set(target, data, **kwargs)

            return _set(path, target, data, **kwargs)

        elif self.parser_name == 'jsonpath_ng':

            def _set(path, target, data, **kwargs):
                return JsonPathParser().parse(path).update(target, data)

            return _set(path, target, data)

        return None


class Path(BaseModel, validate_assignment=True):
    """
    Wrapper for jmespath parser to get/set data from/to an input dictionary.
    """

    path: str = Field('', description="""User-defined path to the data.""")
    parent: Optional['Path'] = Field(None, description="""Parent path.""")
    relative_path: str = Field('', description="""Relative path to the data.""")
    absolute_path: str = Field('', description="""Absolute path to the data.""")
    reduced_path: str = Field('', description="""Reduced absolute path.""")
    parser: PathParser = Field(
        PathParser(), description="""The parser to use to search and set data."""
    )

    @model_validator(mode='before')
    def get_relative_path(cls, values: dict[str, Any]) -> dict[str, Any]:
        relative_path = values.get('path', '')
        parent = values.get('parent')
        match = re.match(r'^\.(.+)|(.+\()\.(.+)', relative_path)
        if match:
            relative_path = ''.join([g for g in match.groups() if g])
        values['relative_path'] = relative_path

        absolute_path = relative_path
        if parent:
            segments = [parent.absolute_path, absolute_path]
            absolute_path = '.'.join([s for s in segments if s != '@' and s])
        values['absolute_path'] = absolute_path

        values['reduced_path'] = re.sub(r'\[.+?\]|\|', '', absolute_path)

        return values

    def is_relative_path(self):
        return self.relative_path != self.path or self.parent is not None

    def get_data(self, source: dict[str, Any], **kwargs) -> Any:
        try:
            return self.parser.get_data(self.relative_path, source, **kwargs)
        except Exception:
            return kwargs.get('default')

    def set_data(self, data: Any, target: dict[str, Any], **kwargs) -> Any:
        cur_data = self.get_data(target, **kwargs)
        update_mode = kwargs.get('update_mode')
        path = self.relative_path

        def update(source: Any, target: Any):
            if not isinstance(source, type(target)):
                return (
                    target if update_mode == 'append' and target is not None else source
                )

            if isinstance(source, dict):
                if update_mode != 'replace':
                    for key in list(source.keys()):
                        target[f'.{key}'] = update(
                            source.get(key), target.get(f'.{key}')
                        )
                return target

            if isinstance(source, list):
                merge = re.match(r'merge(?:@(.+))*', update_mode or '')
                if merge:
                    merge_at = merge.groups()[0]
                    if not merge_at or merge_at == 'start':
                        start = 0
                    elif merge_at == 'last':
                        start = len(source) - len(target)
                    else:
                        start = int(merge_at)
                    if start < 0:
                        start += len(source)
                    for n, d in enumerate(source):
                        if n >= start and n < start + len(target):
                            update(d, target[n - start])
                        else:
                            target.insert(n, d)
                elif update_mode == 'append':
                    for n, d in enumerate(source):
                        target.insert(n, update(d, {}))
                return target

            return target if update_mode == 'append' and target is not None else source

        res = self.parser.set_data(path, target, data, **kwargs)

        update(cur_data, res)

        return res


Path.model_rebuild()


class Data(BaseModel, validate_assignment=True):
    """
    Wrapper for the path to the data or a transformer to extract the data.
    """

    path: Path = Field(None, description="""Path to the data.""")
    transformer: 'Transformer' = Field(
        None, description="""Transformer to extract data."""
    )
    parent: Path = Field(None, description="""Parent path.""")
    path_parser: PathParser = Field(
        None, description="""Parser used to search and set data."""
    )

    @model_validator(mode='before')
    def set_attributes(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get('path') is None and values.get('transformer'):
            transformer = values['transformer']
            if len(transformer.function_args) == 1:
                values['path'] = transformer.function_args[0]
            else:
                values['path'] = Path(path='@')

        if values.get('parent'):
            if values.get('transformer'):
                for arg in values['transformer'].function_args:
                    if arg.is_relative_path():
                        arg.parent = values['parent']
            if values.get('path') and values['path'].is_relative_path():
                values['path'].parent = values['parent']

        if values.get('path_parser'):
            if values.get('path'):
                values['path'].parser = values['path_parser']
            if values.get('transformer'):
                for arg in values['transformer'].function_args:
                    arg.parser = values['path_parser']

        return values

    def get_data(
        self, source_data: dict[str, Any], parser: 'MappingParser' = None, **kwargs
    ) -> Any:
        if self.transformer:
            value = self.transformer.get_data(source_data, parser, **kwargs)
            return self.transformer.normalize_data(value)
        elif self.path:
            return self.path.get_data(
                source_data if self.path.is_relative_path() else parser.data, **kwargs
            )


class BaseMapper(BaseModel):
    """
    Base class for a mapper.
    """

    source: 'Data' = Field(None, description="""Source data.""")
    target: 'Data' = Field(None, description="""Target data.""")
    indices: list[int] | str | None = Field(
        None, description="""List of indices of data to include."""
    )
    order: int = Field(None, description="""Execution order.""")
    remove: bool | None = Field(None, description="""Remove data from source.""")
    cache: bool | None = Field(None, description="""Store the result of the mapper.""")
    all_paths: list[str] = Field(
        [], description="""List of all unindexed abs. paths."""
    )

    def get_data(self, source_data: Any, parser: 'MappingParser', **kwargs) -> Any:
        return None

    def normalize_data(self, data: Any) -> Any:
        return data

    @staticmethod
    def from_dict(dct: dict[str, Any], parent: 'BaseMapper' = None) -> 'BaseMapper':
        """
        Convert dictionary to a BaseMapper object. Dictionary may contain the following
            source: str or Path or tuple or Transformer to extract source data
            target: str or Path object of target data
            mapper:
                str or Path object returns Transfomer with identity function
                Tuple[str, List[str]] returns Transformer
                List[Dict] returns Mapper
            path: str or Path object returns Map object
            function_name: str name of transformation function
            function_args: List[str] of paths of data as arguments to function
            indices: str or List of indices of data to include
                str is function name to evaluate indices
            remove: Remove data from source
        """
        paths: dict[str, Data] = {}
        path_parser = dct.get('path_parser')

        for ptype in ['source', 'target']:
            path = dct.get(ptype)
            if isinstance(path, str):
                path_obj = Data(path=Path(path=path))
            elif isinstance(path, tuple):
                args = [Path(path=p) for p in path[1]]
                path_obj = Data(
                    transformer=Transformer(function_name=path[0], function_args=args)
                )
                if len(path) == 3:
                    path_obj.transformer.function_kwargs = path[2]
                path_obj.transformer.cache = dct.get('cache')
            elif isinstance(path, Data):
                path_obj = path
            else:
                path_obj = None

            if path_obj:
                parent_path = getattr(parent, ptype, None)
                if parent_path is not None:
                    path_obj.parent = parent_path.path
                if path_parser:
                    path_obj.path_parser = PathParser(parser_name=path_parser)
                paths[ptype] = path_obj

        mapper = (
            dct.get('mapper')
            or dct.get('path')
            or (dct.get('function_name'), dct.get('function_args'))
        )
        obj: BaseMapper = BaseMapper()
        if isinstance(mapper, tuple) and None in mapper:
            return obj

        def add_path_attrs(path: Path):
            if path.is_relative_path():
                source_path = paths.get('source', parent.source if parent else None)
                if source_path:
                    path.parent = source_path.path
            if path_parser:
                path.parser = PathParser(parser_name=path_parser)

        if isinstance(mapper, str | Path):
            path = Path(path=mapper) if isinstance(mapper, str) else mapper
            obj = Transformer()
            add_path_attrs(path)
            obj.function_args.append(path)

        elif (
            isinstance(mapper, tuple | list)
            and len(mapper) in [2, 3]
            and isinstance(mapper[0], str)
            and isinstance(mapper[1], list)
        ):
            function_args = []
            for v in mapper[1]:
                arg = v
                if isinstance(v, str):
                    arg = Path(path=v)
                add_path_attrs(arg)
                function_args.append(arg)
            obj = Transformer(function_name=mapper[0], function_args=function_args)
            if len(mapper) == 3:
                obj.function_kwargs = mapper[2]

        elif isinstance(mapper, list) and isinstance(mapper[0], dict):
            obj = Mapper()
        else:
            LOGGER.error('Unknown mapper type.')

        for key in ['indices', 'remove', 'cache']:
            if dct.get(key) is not None:
                setattr(obj, key, dct.get(key))
        if paths.get('source'):
            obj.source = paths.get('source')
        if paths.get('target'):
            obj.target = paths.get('target')

        if isinstance(obj, Mapper):
            mappers = []
            for v in mapper:
                m = BaseMapper.from_dict(v, obj)
                mappers.append(m)
            obj.mappers = mappers

        return obj

    def get_required_paths(self) -> list[str]:
        def get_path_segments(parsed: dict[str, Any]) -> list[str]:
            segments: list[str] = []
            value = parsed.get('value')
            ptype = parsed.get('type')

            if ptype == 'comparator':
                return segments

            if value and ptype == 'field':
                segments.append(value)

            for children in parsed.get('children', []):
                if not isinstance(children, dict):
                    continue
                segments.extend(get_path_segments(children))

            return segments

        def filter_path(path: str) -> list[str]:
            parsed = JmespathParser().parse(path).parsed
            segments = get_path_segments(parsed)
            return ['.'.join(segments[:n]) for n in range(1, len(segments) + 1)]

        def get_paths(mapper: BaseMapper) -> list[str]:
            paths = []
            if mapper.source and mapper.source.transformer:
                for path in mapper.source.transformer.function_args:
                    paths.extend(filter_path(path.absolute_path))

            if isinstance(mapper, Mapper):
                for sub_mapper in mapper.mappers:
                    paths.extend(get_paths(sub_mapper))

            elif isinstance(mapper, Transformer):
                for path in mapper.function_args:
                    paths.extend(filter_path(path.absolute_path))

            return paths

        return list(set(get_paths(self)))


class Transformer(BaseMapper):
    """
    Mapper to perform a transformation of the data.

    A static method with function_name should be implemented in the parser class.

        class Parser(MappingParser):
            @staticmethod
            def get_eigenvalues_energies(array: np.ndarray, n_spin: int, n_kpoints: int):
                array = np.transpose(array)[0].T
                return np.reshape(array, (n_spin, n_kpoints, len(array[0])))

    If function is not defined, identity transformation is applied.
    """

    function_name: str = Field(
        '', description="""Name of the function defined in the parser."""
    )
    function_args: list[Path] = Field(
        [], description="""Paths to the data as arguments to the function."""
    )
    function_kwargs: dict[str, Any] = Field(
        {}, description="""Keyword args to pass to function."""
    )
    order: int = 1

    def get_data(
        self, source_data: dict[str, Any], parser: 'MappingParser', **kwargs
    ) -> Any:
        remove: bool = kwargs.get('remove', self.remove)
        func = (
            getattr(parser, self.function_name, None)
            if self.function_name
            else lambda x: x
        )
        args = [
            m.get_data(
                source_data if m.is_relative_path() else parser.data,
                pop=remove and self.all_paths.count(m.reduced_path) <= 1,
            )
            for m in self.function_args
        ]
        try:
            return (
                func(*args)
                if not self.function_kwargs
                else func(*args, **self.function_kwargs)
            )
        except Exception:
            # if self.function_name == 'get_positions':
            #     raise
            return None


Data.model_rebuild()


class Mapper(BaseMapper, validate_assignment=True):
    """
    Mapper for nested mappers.
    """

    mappers: list[BaseMapper] = Field([], description="""List of sub mappers.""")
    order: int = 0
    __cache: dict[str, Any] = {}

    @model_validator(mode='before')
    def set_attributes(cls, values: dict[str, Any]) -> dict[str, Any]:
        def get_paths(mapper: BaseMapper) -> list[str]:
            paths = []
            if isinstance(mapper, Transformer):
                paths.extend([p.reduced_path for p in mapper.function_args])
            elif isinstance(mapper, Mapper):
                for m in mapper.mappers:
                    paths.extend(get_paths(m))
            return paths

        def set_paths(mapper: BaseMapper, paths: list[str]):
            mapper.all_paths = paths
            if isinstance(mapper, Mapper):
                for m in mapper.mappers:
                    set_paths(m, paths)

        def set_remove(mapper: BaseMapper, remove: bool):
            mapper.remove = remove
            if isinstance(mapper, Mapper):
                for m in mapper.mappers:
                    set_remove(m, remove)

        paths = []
        for mapper in values.get('mappers', []):
            paths.extend(get_paths(mapper))

        # propagate all properties to all mappers
        for mapper in values.get('mappers', []):
            if not values.get('all_paths'):
                set_paths(mapper, paths)
            set_remove(mapper, values.get('remove'))

        if not values.get('all_paths'):
            values['all_paths'] = paths

        return values

    def get_data(
        self, source_data: dict[str, Any], parser: 'MappingParser', **kwargs
    ) -> Any:
        dct = {}
        for mapper in self.mappers:
            data = source_data
            if mapper.source:
                data = None
                if mapper.source.transformer and mapper.source.transformer.cache:
                    data = self.__cache.get(mapper.source.transformer.function_name)
                if data is None:
                    data = mapper.source.get_data(source_data, parser, **kwargs)
                    if mapper.source.transformer and mapper.source.transformer.cache:
                        self.__cache.setdefault(
                            mapper.source.transformer.function_name, data
                        )

            def is_not_value(value: Any) -> bool:
                if isinstance(value, np.ndarray):
                    return value.size == 0
                if hasattr(value, 'magnitude'):
                    return is_not_value(value.magnitude)

                not_value: Any
                for not_value in [None, [], {}]:
                    test = value == not_value
                    result = test.any() if isinstance(test, np.ndarray) else test
                    if result:
                        return bool(result)

                return False

            indices = mapper.indices
            if isinstance(indices, str):
                indices = getattr(parser, indices, [])
                if callable(indices):
                    indices = indices()

            value: list[Any] = []
            if isinstance(mapper, Transformer) and mapper.cache:
                value = self.__cache.get(mapper.function_name, value)

            if not value:
                for n, d in enumerate(data if isinstance(data, list) else [data]):
                    v = mapper.get_data(d, parser, **kwargs)
                    if indices and n not in indices:
                        continue
                    if not is_not_value(v):
                        value.append(v)
                if value and mapper.cache and isinstance(mapper, Transformer):
                    self.__cache.setdefault(mapper.function_name, value)
            if value:
                normalized_value = [mapper.normalize_data(v) for v in value]
                dct[mapper.target.path.path] = (
                    normalized_value[0] if mapper.indices is None else normalized_value
                )
        return dct

    def sort(self, recursive=True):
        self.mappers.sort(key=lambda m: m.order)
        if recursive:
            for mapper in self.mappers:
                if isinstance(mapper, Mapper):
                    mapper.sort()


Mapper.model_rebuild()


class MappingParser(ABC):
    """
    A generic parser class to convert the contents of a file specified by filepath to a
    dictionary. The data object is the abstract interface to the data which can defined
    by implementing the load_file method.

    If attributes are parsed, the data is wrapped in a dictionary with the attribute keys
    prefixed by attribute_prefix while the value can be accesed by value_key.

    data = {
      'a' : {
        'b': [
          {'@name': 'item1', '__value': 'name'},
          {'@name': 'item2', '__value': 'name2'}
        ]
      }
    }
    a.b[?"@name"==\'item2\'].__value
    >> name2

    A mapping parser can be converted to another mapping parser using the convert method
    by providing a mapper object.

    Attributes:
        parse_only_required
            Parse only data required by target parser.
        attribute_prefix
            Added to start of key to denote it is a data attribute.
        value_key
            Key to the value of the data.
    """

    parse_only_required: bool = False
    attribute_prefix: str = '@'
    value_key: str = '__value'
    logger = get_logger(__name__)

    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)
        self._mapper: BaseMapper = kwargs.get('mapper')
        self._filepath: str = kwargs.get('filepath')
        self._data: dict[str, Any] = kwargs.get('data', {})
        self._data_object: Any = kwargs.get('data_object')
        self._required_paths: list[str] = kwargs.get('required_paths', [])

    @abstractmethod
    def load_file(self) -> Any:
        return {}

    @abstractmethod
    def to_dict(self, **kwargs) -> dict[str, Any]:
        return {}

    @abstractmethod
    def from_dict(self, dct: dict[str, Any]):
        pass

    def build_mapper(self) -> BaseMapper:
        return Mapper()

    @property
    def filepath(self) -> str:
        return self._filepath

    @filepath.setter
    def filepath(self, value: str):
        self._filepath = value
        self._data_object = None
        self._data = None

    @property
    def data(self):
        if not self._data:
            self._data = self.to_dict()
        return self._data

    @property
    def data_object(self):
        if self._data_object is None:
            self._data_object = self.load_file()
        return self._data_object

    @data_object.setter
    def data_object(self, value: Any):
        self._data_object = value
        self._data = None
        self._filepath = None

    @property
    def mapper(self) -> BaseMapper:
        if self._mapper is None:
            self._mapper = self.build_mapper()
        return self._mapper

    @mapper.setter
    def mapper(self, value: BaseMapper):
        self._mapper = value

    def set_data(self, data: Any, target: dict[str, Any], **kwargs) -> None:
        if isinstance(data, dict):
            for key in list(data.keys()):
                path = Path(path=key)
                new_data = path.set_data(
                    data.pop(key) if kwargs.get('remove') else data[key],
                    data if path.is_relative_path() else target,
                    update_mode=kwargs.get('update_mode', 'merge'),
                )
                self.set_data(new_data, target, remove=True)

        elif isinstance(data, list):
            for val in data:
                self.set_data(val, target, **kwargs)

    def get_data(
        self,
        mapper: BaseMapper,
        source_data: dict[str, Any],
    ) -> Any:
        return mapper.get_data(source_data, self)

    def convert(
        self,
        target: 'MappingParser',
        mapper: 'BaseMapper' = None,
        update_mode: str = 'merge',
        remove: bool = False,
    ):
        if mapper is None:
            mapper = target.mapper
        if self.parse_only_required and mapper and not self._required_paths:
            self._required_paths = mapper.get_required_paths()
        source_data = self.data
        if mapper.source:
            source_data = mapper.source.get_data(self.data, self)
        result = mapper.get_data(source_data, self, remove=remove)
        target.set_data(result, target.data, update_mode=update_mode)
        target.from_dict(target.data)

    def close(self):
        if hasattr(self._data_object, 'close'):
            self._data_object.close()
        self._data_object = None
        self._data = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        string = f'{self.__class__.__name__}'
        if self.filepath:
            string += f'({os.path.basename(self.filepath)})'
        if self._data_object:
            string += f': {type(self._data_object).__name__}'
        if self._data:
            keys = list(self._data.keys())
            keys = keys[: min(len(keys), 5)]
            string += f' -> data.keys: {", ".join([key for key in keys])}'
            if len(self._data.keys()) > 5:
                string += '...'
        return string


class MetainfoBaseMapper(BaseMapper):
    @staticmethod
    def from_dict(dct: dict[str, Any], parent: BaseMapper = None) -> 'BaseMapper':
        parent = BaseMapper.from_dict(dct) if parent is None else parent

        if isinstance(parent, Transformer):
            transformer = MetainfoTransformer()
            for key in parent.model_fields.keys():
                val = getattr(parent, key)
                if val is not None:
                    setattr(transformer, key, val)
            for key in ['unit', 'search']:
                if dct.get(key):
                    setattr(transformer, key, dct.get(key))
            return transformer
        elif isinstance(parent, Mapper):
            mdct = dct.get('mapper')
            mapper = MetainfoMapper()
            for key in parent.model_fields.keys():
                val = getattr(parent, key)
                if val is not None:
                    setattr(mapper, key, val)
            if dct.get('m_def'):
                mapper.m_def = dct.get('m_def')
            for n, obj in enumerate(parent.mappers):
                parent.mappers[n] = MetainfoBaseMapper.from_dict(mdct[n], obj)
            mapper.mappers = parent.mappers
            return mapper
        return parent


class MetainfoMapper(MetainfoBaseMapper, Mapper):
    m_def: str = Field(None, description="""Section definition.""")

    def get_data(
        self, source_data: dict[str, Any], parser: MappingParser, **kwargs
    ) -> Any:
        dct = super().get_data(source_data, parser, **kwargs)
        if self.m_def:
            dct['.m_def'] = self.m_def
        return dct


class MetainfoTransformer(MetainfoBaseMapper, Transformer):
    unit: str = Field(None, description="""Pint unit to be applied to value.""")
    search: str = Field(None, description="""Path to search value.""")

    def normalize_data(self, value: Any):
        if self.search:
            path = Path(path=self.search)
            value = path.get_data(value)
        if self.unit is not None and value is not None and not hasattr(value, 'units'):
            value = value * ureg(self.unit)
        return value


class MetainfoParser(MappingParser):
    """
    A parser for metainfo sections.
    """

    def __init__(self, **kwargs):
        self._annotation_key: str = kwargs.get('annotation_key', 'mapping')
        self.max_nested_level: int = 1
        super().__init__(**kwargs)

    @property
    def annotation_key(self) -> str:
        return self._annotation_key

    @annotation_key.setter
    def annotation_key(self, value):
        self._annotation_key = value
        self._mapper = None

    def load_file(self) -> MSection:
        if self._data_object is not None:
            with open(self.filepath) as f:
                return self._data_object.m_from_dict(json.load(f))
        elif self.filepath:
            try:
                archive = EntryArchive()
                ArchiveParser().parse(self.filepath, archive)
                return archive
            except Exception:
                self.logger.errror('Error loading archive file.')
        return None

    def to_dict(self, **kwargs) -> dict[str, Any]:
        if self.data_object is not None:
            return self.data_object.m_to_dict()
        return {}

    def from_dict(self, dct: dict[str, Any], root: MSection = None) -> None:
        # if self.data_object is not None:
        #     self.data_object = self.data_object.m_from_dict(dct)
        # return

        # TODO this is a temporary fix for nomad_simulations  PhysicalProperty
        # error with m_from_dict
        if self.data_object is None:
            return

        if root is None:
            root = self.data_object

        for key, val in dct.items():
            if not hasattr(root, key):
                continue

            section = getattr(root.m_def.section_cls, key)
            if isinstance(section, SubSection):
                val_list = [val] if isinstance(val, dict) else val
                m_def = val_list[-1].get('m_def')
                section_def = section.sub_section
                if m_def is not None and m_def != section.qualified_name():
                    for isection in section.sub_section.all_inheriting_sections:
                        if isection.qualified_name() == m_def:
                            section_def = isection
                            break

                for n, val_n in enumerate(val_list):
                    quantities = section_def.all_quantities
                    try:
                        sub_section = root.m_get_sub_section(section, n)
                    except Exception:
                        sub_section = None
                    if sub_section is None:
                        sub_section = section_def.section_cls(
                            **{
                                n: val_n.get(n)
                                for n, q in quantities.items()
                                if not q.derived and n in val_n and n != 'value'
                            }
                        )
                        root.m_add_sub_section(section, sub_section)
                    self.from_dict(val_n, sub_section)
                    value = val_n.get('value')
                    if value is not None:
                        sub_section.value = value
                continue

            if key == 'm_def' or key == 'value':
                continue

            try:
                root.m_set(root.m_get_quantity_definition(key), val)
            except Exception:
                pass

    def build_mapper(self, max_level: int = None) -> BaseMapper:
        """
        Builds a mapper for source data from the another parser with path or operator
        specified in metainfo annotation with key annotation_key. The target path is
        given by the sub section key.
        """

        def fill_mapper(
            mapper: dict[str, Any],
            annotation: MapperAnnotation,
            attributes: list[str],
        ) -> None:
            for key in attributes:
                value = getattr(annotation, key, None)
                if value is not None:
                    mapper.setdefault(key, value)

        def build_section_mapper(
            section: SubSection | MSection, level: int = 0
        ) -> dict[str, Any]:
            mapper: dict[str, Any] = {}
            if level >= (max_level or self.max_nested_level):
                return mapper

            section_def = (
                section.sub_section
                if isinstance(section, SubSection)
                else section.m_def
            )

            if not section_def:
                return mapper

            # try to get annotation from sub-section
            annotation: MapperAnnotation = (
                (section if isinstance(section, SubSection) else section_def)
                .m_get_annotations(MAPPING_ANNOTATION_KEY, {})
                .get(self.annotation_key)
            )

            if not annotation:
                # get it from def
                annotation = section_def.m_get_annotations(
                    MAPPING_ANNOTATION_KEY, {}
                ).get(self.annotation_key)

            if isinstance(section, SubSection) and not annotation:
                # search also all inheriting sections
                for inheriting_section in section_def.all_inheriting_sections:
                    annotation = inheriting_section.m_get_annotations(
                        MAPPING_ANNOTATION_KEY, {}
                    ).get(self.annotation_key)
                    if annotation:
                        # TODO this does not work as it will applies to base class
                        # section.sub_section = inheriting_section
                        # TODO this is a hacky patch, metainfo should have an alternative
                        # way to resolve the sub-section def
                        mapper['m_def'] = inheriting_section.qualified_name()
                        section_def = inheriting_section
                        break

            if not annotation:
                return mapper

            fill_mapper(mapper, annotation, ['remove', 'cache', 'path_parser'])
            mapper['source'] = annotation.mapper

            mapper['mapper'] = []
            for name, quantity_def in section_def.all_quantities.items():
                qannotation = quantity_def.m_get_annotations(
                    MAPPING_ANNOTATION_KEY, {}
                ).get(self.annotation_key)
                if qannotation:
                    quantity_mapper = {
                        'mapper': qannotation.mapper,
                        'target': f'{"" if section == self.data_object else "."}{name}',
                    }
                    fill_mapper(
                        quantity_mapper,
                        qannotation,
                        ['remove', 'cache', 'path_parser', 'unit', 'search'],
                    )
                    mapper['mapper'].append(quantity_mapper)

            all_ids = [section_def.definition_id]
            all_ids.extend([s.definition_id for s in section_def.all_base_sections])
            for name, sub_section in section_def.all_sub_sections.items():
                # avoid recursion
                # if sub_section.sub_section.definition_id in all_ids:
                #     continue
                # allow recursion up to max_level
                nested = sub_section.sub_section.definition_id in all_ids
                sub_section_mapper = build_section_mapper(
                    sub_section, level + (1 if nested else 0)
                )
                if sub_section_mapper and sub_section_mapper.get('mapper'):
                    sub_section_mapper['target'] = (
                        f'{"" if section == self.data_object else "."}{name}'
                    )
                    sub_section_mapper['indices'] = [] if sub_section.repeats else None
                    sannotation = sub_section.m_get_annotations(
                        MAPPING_ANNOTATION_KEY, {}
                    ).get(self.annotation_key)
                    if sannotation:
                        sub_section_mapper['source'] = sannotation.mapper
                        fill_mapper(
                            sub_section_mapper,
                            sannotation,
                            ['remove', 'cache', 'path_parser', 'indices'],
                        )
                    mapper['mapper'].append(sub_section_mapper)

            return mapper

        dct = build_section_mapper(self.data_object)
        return MetainfoMapper.from_dict(dct)


class HDF5Parser(MappingParser):
    """
    Mapping parser for HDF5.
    """

    def load_file(self, **kwargs) -> h5py.Group:
        try:
            filepath = kwargs.get('file', self.filepath)
            mode = (
                'w'
                if isinstance(filepath, str) and not os.path.isfile(filepath)
                else 'r'
            )
            return h5py.File(filepath, kwargs.get('mode', mode))
        except Exception:
            self.logger.error('Cannot read HDF5 file.')

    def to_dict(self, **kwargs) -> dict[str, Any]:
        if self.data_object is None:
            return {}

        def set_attributes(val: h5py.Dataset | h5py.Group, dct: dict[str, Any]):
            for name, attr in val.attrs.items():
                dct[f'{self.attribute_prefix}{name}'] = (
                    attr.tolist() if hasattr(attr, 'tolist') else attr
                )

        def group_to_dict(
            group: h5py.Group, root: dict[str, Any] | list[dict[str, Any]]
        ):
            for key, val in group.items():
                key = int(key) if key.isdecimal() else key
                path = '.'.join(
                    [p for p in val.name.split('/') if not p.isdecimal() and p]
                )
                if self._required_paths and path not in self._required_paths:
                    continue
                if isinstance(root, list) and isinstance(val, h5py.Group):
                    group_to_dict(val, root[key])
                    set_attributes(val, root[key])
                elif isinstance(root, dict) and isinstance(val, h5py.Group):
                    default: list[dict[str, Any]] = [
                        {} if k.isdecimal() else None for k in val.keys()
                    ]
                    group_to_dict(
                        val, root.setdefault(key, {} if None in default else default)
                    )
                    if not root[key]:
                        root[key] = {}
                    set_attributes(val, root[key])
                elif isinstance(val, h5py.Dataset):
                    data = val[()]
                    v = (
                        data.astype(str if data.dtype == np.object_ else data.dtype)
                        if isinstance(data, np.ndarray)
                        else data.decode()
                        if isinstance(data, bytes)
                        else data
                    )
                    v = v.tolist() if hasattr(v, 'tolist') else v
                    attrs = list(val.attrs.keys())
                    if attrs:
                        root[key] = {self.value_key: v}
                        set_attributes(val, root[key])
                    else:
                        root[key] = v  # type: ignore
            return root

        dct: dict[str, Any] = {}
        group_to_dict(self.data_object, dct)
        return dct

    def from_dict(self, dct: dict[str, Any]) -> None:
        if self._data_object is not None:
            self._data_object.close()

        root = self.load_file(mode='a', file=self.filepath or BytesIO())

        def dict_to_hdf5(dct: dict[str, Any], root: h5py.Group) -> h5py.Group:
            for key, val in dct.items():
                if key.startswith(self.attribute_prefix):
                    root.attrs[key.lstrip(self.attribute_prefix)] = val
                elif isinstance(val, dict) and self.value_key not in val:
                    group = root.require_group(key)
                    dict_to_hdf5(val, group)
                elif isinstance(val, list) and val and isinstance(val[0], dict):
                    data = {}
                    for n, v in enumerate(val):
                        if self.value_key not in v:
                            group = root.require_group(f'{key}/{n}')
                            dict_to_hdf5(v, group)
                        else:
                            data[f'{key}/{n}'] = v
                    dict_to_hdf5(data, root)
                else:
                    attrs = val if isinstance(val, dict) else {}
                    v = attrs.get(self.value_key, None) if attrs else val
                    if v is None:
                        continue

                    if isinstance(v, list):
                        v = np.array(v)

                    shape = v.shape if hasattr(v, 'shape') else ()
                    dtype = v.dtype.type if hasattr(v, 'dtype') else type(v)
                    if dtype in [np.str_, str]:
                        dtype = h5py.string_dtype()
                    dataset = root.require_dataset(key, shape, dtype)
                    dataset[...] = v.tolist() if hasattr(v, 'tolist') else v
                    for name, attr in attrs.items():
                        if name == self.value_key:
                            continue
                        dataset.attrs[name.lstrip(self.attribute_prefix)] = attr

            return root

        self._data_object = dict_to_hdf5(dct, root)


class XMLParser(MappingParser):
    """
    A mapping parser for XML files. The contents of the xml file are converted into
    a dictionary using the lxml module (see https://lxml.de/).
    """

    def from_dict(self, dct: dict[str, Any]) -> None:
        def to_string(val: Any) -> str | None:
            val = val.tolist() if hasattr(val, 'tolist') else val
            if not isinstance(val, list):
                return str(val)
            string = ''
            for v in val:
                if not isinstance(v, str | float | int):
                    return None
                string += f' {v}'
            return string.strip()

        def data_to_element(
            tag: str, data: Any, root: etree._Element = None
        ) -> etree._Element:
            if tag.startswith(self.attribute_prefix) and root is not None:
                root.set(tag.lstrip(self.attribute_prefix), data)
            elif tag.startswith(self.value_key) and root is not None:
                root.text = to_string(data)
            elif isinstance(data, dict):
                root = (
                    etree.Element(tag) if root is None else etree.SubElement(root, tag)
                )
                for key, val in data.items():
                    data_to_element(key, val, root)
            elif isinstance(data, list):
                string = to_string(data)
                if string is not None:
                    element = etree.SubElement(root, tag)
                    element.text = string
                else:
                    for val in data:
                        data_to_element(tag, val, root)
            elif hasattr(data, 'tolist'):
                data_to_element(tag, data.tolist(), root)
            else:
                element = etree.SubElement(root, tag)
                element.text = to_string(data)
            return root

        self._data_object = data_to_element('root', dct).getchildren()[0]

    def to_dict(self, **kwargs) -> dict[str, Any]:
        def convert(text: str) -> Any:
            val = text.strip()
            try:
                val_array = np.array(val.split(), dtype=float)
                if np.all(np.mod(val_array, 1) == 0):
                    val_array = np.array(val_array, dtype=int)
                val_array = val_array.tolist()
                return val_array[0] if len(val_array) == 1 else val_array
            except Exception:
                return val

        stack: list[dict[str, Any]] = []
        results: dict[str, Any] = {}
        if self.filepath is None:
            return results

        current_path = ''
        # TODO determine if iterparse is better than iterwalk
        with open(self.filepath, 'rb') as f:
            for event, element in etree.iterparse(f, events=('start', 'end')):
                tag = element.tag
                if event == 'start':
                    current_path = tag if not current_path else f'{current_path}.{tag}'
                    if (
                        self._required_paths
                        and current_path not in self._required_paths
                    ):
                        continue
                    stack.append({tag: {}})
                else:
                    path = current_path
                    current_path = current_path.rsplit('.', 1)[0]
                    if self._required_paths and path not in self._required_paths:
                        continue
                    data = stack.pop(-1)
                    text = element.text.strip() if element.text else None
                    attrib = element.attrib
                    if attrib:
                        data.setdefault(tag, {})
                        data[tag].update(
                            (f'{self.attribute_prefix}{k}', v)
                            for k, v in attrib.items()
                        )
                    if text:
                        value = convert(text)
                        if attrib or data[tag]:
                            data[tag][self.value_key] = value
                        else:
                            data[tag] = value
                    if stack and data:
                        parent = stack[-1][list(stack[-1].keys())[0]]
                        if tag in parent:
                            if (
                                isinstance(data[tag], list)
                                and isinstance(parent[tag], list)
                                and parent[tag]
                                and not isinstance(parent[tag][0], list)
                            ):
                                parent[tag] = [parent[tag]]
                            if isinstance(parent[tag], list):
                                parent[tag].append(data[tag])
                            else:
                                parent[tag] = [
                                    parent[tag],
                                    data[tag],
                                ]
                        else:
                            # parent[tag] = [data[tag]] if attrib else data[tag]
                            parent[tag] = data[tag]
                    else:
                        results = data
        return results

    def load_file(self) -> etree._Element:
        try:
            return etree.parse(self.filepath)
        except Exception:
            self.logger.error('Cannot read XML file')


class TextParser(MappingParser):
    """
    Interface to text file parser.
    """

    text_parser: TextFileParser = None

    def to_dict(self, **kwargs) -> dict[str, Any]:
        if self.data_object:
            self.data_object.parse()
            return self.data_object._results
        return {}

    def from_dict(self, dct: dict[str, Any]):
        raise NotImplementedError

    def load_file(self) -> Any:
        if self.filepath:
            self.text_parser.findlazy = True
            self.text_parser.mainfile = self.filepath
        return self.text_parser


if __name__ == '__main__':
    from nomad.parsing.file_parser.mapping_parser import MetainfoParser
    from tests.parsing.test_mapping_parser import (
        BSection,
        ExampleHDF5Parser,
        ExampleSection,
    )

    with MetainfoParser() as archive_parser, ExampleHDF5Parser() as hdf5_parser:
        archive_parser.annotation_key = 'hdf5'
        archive_parser.data_object = ExampleSection(b=[BSection(v=np.eye(2))])

        d = dict(
            g=dict(
                g1=dict(v=[dict(d=np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))]),
                v=['x', 'y', 'z'],
                g=dict(
                    c1=dict(
                        i=[4, 6],
                        f=[
                            {'@index': 0, '__value': 1},
                            {'@index': 2, '__value': 2},
                            {'@index': 1, '__value': 1},
                        ],
                        d=[dict(e=[3, 0, 4, 8, 1, 6]), dict(e=[1, 7, 8, 3, 9, 1])],
                    ),
                    c=dict(
                        v=[dict(d=np.eye(3), e=np.zeros(3)), dict(d=np.ones((3, 3)))]
                    ),
                ),
            )
        )

        hdf5_parser.from_dict(d)

        hdf5_parser.convert(archive_parser)
