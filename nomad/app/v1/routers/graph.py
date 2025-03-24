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

from enum import Enum

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import ORJSONResponse

from nomad.app.v1.models.graph import GraphRequest, GraphResponse
from nomad.graph.graph_reader import (
    ConfigError,
    GeneralReader,
    MongoReader,
    Token,
    UserReader,
)
from nomad.graph.lazy_wrapper import LazyWrapper

from ..models import User
from .auth import create_user_dependency
from .entries import EntriesArchive

router = APIRouter()


class APITag(str, Enum):
    DEFAULT = 'graph'


def unwrap_response(result):
    if isinstance(result, dict):
        for key, value in result.items():
            if isinstance(value, LazyWrapper):
                result[key] = value.to_json()
            elif key != Token.ARCHIVE:
                unwrap_response(value)
    elif isinstance(result, list):
        for idx, value in enumerate(result):
            if isinstance(value, LazyWrapper):
                result[idx] = value.to_json()
            else:
                unwrap_response(value)


class GraphJSONResponse(ORJSONResponse):
    def render(self, content):
        content.pop(GeneralReader.__CACHE__, None)

        unwrap_response(content)
        return super().render(content)


def relocate_children(request):
    if not isinstance(request, dict) or not request:
        return
    request.update(request.pop('m_children', {}))
    for child in request.values():
        relocate_children(child)


@router.post(
    '/raw_query',
    tags=[APITag.DEFAULT],
    summary='Query the database with a graph style without verification.',
    description='Query the database with a graph style without verification.',
    response_class=GraphJSONResponse,
)
async def raw_query(query=Body(...), user: User = Depends(create_user_dependency())):
    relocate_children(query)
    with MongoReader(query, user=user) as reader:
        return GraphJSONResponse(await reader.read())


@router.post(
    '/query',
    tags=[APITag.DEFAULT],
    summary='Query the database with a graph style.',
    description='Query the database with a graph style.',
    response_model=GraphResponse,
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
)
async def basic_query(
    query: GraphRequest = Body(...),
    user: User = Depends(create_user_dependency()),
):
    try:
        query_dict = query.dict(
            exclude_none=True, exclude_unset=True, exclude_defaults=True
        )
        relocate_children(query_dict)
        with MongoReader(query_dict, user=user) as reader:
            response: dict = await reader.read()
    except ConfigError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:
        raise HTTPException(422, detail=str(e))

    return GraphJSONResponse(response)


@router.post(
    '/archive/query',
    tags=[APITag.DEFAULT],
    summary='Search entries and access their archives',
    response_class=GraphJSONResponse,
)
async def archive_query(
    data: EntriesArchive, user: User = Depends(create_user_dependency())
):
    graph_dict: dict = {Token.SEARCH: {'m_request': {'query': {}}}}
    root_request: dict = graph_dict[Token.SEARCH]['m_request']['query']

    if data.pagination:
        root_request['pagination'] = data.pagination
    if data.query:
        root_request['query'] = data.query
    if data.owner:
        root_request['owner'] = data.owner

    if data.required is None:
        graph_dict[Token.SEARCH]['m_request']['directive'] = 'plain'
    else:
        graph_dict[Token.SEARCH]['*'] = {Token.ENTRIES: {Token.ARCHIVE: data.required}}

    if not root_request:
        del graph_dict[Token.SEARCH]['m_request']['query']

    with UserReader(graph_dict, user=user) as reader:
        response: dict = await reader.read(user.user_id if user else '')

    return GraphJSONResponse(response)
