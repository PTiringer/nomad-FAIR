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

from collections.abc import Callable
from enum import Enum
from inspect import Parameter, Signature
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi import Query as FastApiQuery
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestFormStrict

from nomad import datamodel
from nomad.auth import keycloak
from nomad.auth.keycloak import KeycloakError, OIDCToken
from nomad.auth.tokens import (
    AppToken,
    SignatureToken,
    generate_simple_token,
    get_user_from_keycloak_token,
    get_user_from_simple_token,
    get_user_from_upload_token,
)
from nomad.config import config
from nomad.config.models.config import ModeEnum
from nomad.utils import get_logger

from ..common import root_path
from ..models import HTTPExceptionModel, User
from ..utils import create_responses

logger = get_logger(__name__)

router = APIRouter()


class APITag(str, Enum):
    OIDC = 'OpenID Connect Token Endpoints'
    CUSTOM = 'NOMAD Custom Token Endpoints'


# Functions for resolving User from tokens

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f'{root_path}/auth/token', auto_error=False
)


def _resolve_user(
    *,
    required: bool = False,
    request: Request | None = None,
    keycloak_token: str | None = None,
    simple_token: str | None = None,
    upload_token: str | None = None,
    upload_token_query_param: str | None = None,  # DEPRECATED: via query parameters
) -> User | None:
    # Require upload token via header instead of query parameter
    if upload_token_query_param is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Passing upload token via query parameter 'token' is no longer supported. "
                "Please use the 'Upload-Token' header instead."
            ),
        )

    # `config.oasis.require_authentication` would require authentication globally
    required = required or config.oasis.require_authentication

    # Resolve user from token
    user: User | None = None
    if user is None and simple_token:
        try:
            unverified_payload = jwt.decode(
                simple_token, options={'verify_signature': False}
            )
            # This is used to distinguish simple token from keycloak token:
            # simple token only has `user/exp` in payload,
            # while the keycloak has much more (RFC 7519)
            if unverified_payload.keys() == {'user', 'exp'}:
                user = get_user_from_simple_token(simple_token)
        except jwt.DecodeError as e:  # token could be non-JWT (for testing)
            logger.error('Failed to decode simple token', exc_info=e)

    if user is None and (keycloak_token or request):
        user = get_user_from_keycloak_token(keycloak_token, request=request)

    if user is None and upload_token:
        user = get_user_from_upload_token(upload_token)

    if user is None and config.tests.assume_auth_for_username:
        if config.services.mode == ModeEnum.PRODUCTION:
            raise ValueError(
                'assume_auth_for_username is test-only and not allowed in production mode'
            )
        user = datamodel.User.get(username=config.tests.assume_auth_for_username)

    # Check if user is resolved only when required
    if required and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication required.',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    # `allowed_users` would enforce an explicit whitelist of users
    if config.oasis.allowed_users is not None:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Authentication is required for this Oasis',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        if (
            user.email not in config.oasis.allowed_users
            and user.username not in config.oasis.allowed_users
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You are not authorized to access this Oasis',
            )

    # Validate user against recording
    if user is not None:
        try:
            if datamodel.User.get(user.user_id) is None:
                raise ValueError('User not found in database')
        except Exception as e:
            logger.error('API usage by unknown user.', exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You are logged in with an unknown user',
            ) from e

    return user


def get_current_user(
    *,
    required: bool = False,
    allow_keycloak_token: bool = True,
    allow_simple_token: bool = True,
    allow_upload_token: bool = False,
) -> Callable:
    """
    Resolve the authenticated user from keycloak/simple/upload tokens.
    """

    def current_user(**kwargs) -> User | None:
        return _resolve_user(
            required=required,
            request=kwargs.get('request'),
            keycloak_token=kwargs.get('keycloak_token'),
            simple_token=kwargs.get('simple_token'),
            upload_token=kwargs.get('upload_token'),
            upload_token_query_param=kwargs.get('upload_token_query_param'),
        )

    parameters: list[Parameter] = []

    if allow_keycloak_token:
        parameters.append(
            Parameter(
                name='keycloak_token',
                annotation=str,
                default=Depends(oauth2_scheme),
                kind=Parameter.KEYWORD_ONLY,
            )
        )
        parameters.append(
            Parameter(
                name='request',
                annotation=Request,  # for getting keycloak token from cookie
                kind=Parameter.KEYWORD_ONLY,
            )
        )

    if allow_simple_token:
        parameters.append(
            Parameter(
                name='simple_token',
                annotation=str,
                default=Depends(oauth2_scheme),
                kind=Parameter.KEYWORD_ONLY,
            )
        )

    if allow_upload_token:
        parameters.append(
            Parameter(
                name='upload_token',
                annotation=str,
                default=Header(
                    None,
                    alias='Upload-Token',
                    description='HMAC-signed upload token.',
                ),
                kind=Parameter.KEYWORD_ONLY,
            )
        )
        parameters.append(
            Parameter(
                name='upload_token_query_param',
                annotation=str,
                default=FastApiQuery(
                    None,
                    alias='token',
                    description='[DEPRECATED] Legacy upload token query parameter. '
                    'Use the "Upload-Token" header instead.',
                ),
                kind=Parameter.KEYWORD_ONLY,
            )
        )

    current_user.__signature__ = Signature(parameters)  # type: ignore[attr-defined]
    return current_user


# OpenID Connect (OIDC) endpoints


_bad_credentials_response = (
    status.HTTP_401_UNAUTHORIZED,
    {
        'model': HTTPExceptionModel,
        'description': 'Unauthorized. The provided credentials were not recognized.',
    },
)


@router.post(
    '/token',
    tags=[APITag.OIDC],
    summary='Get an OIDC token response',
    responses=create_responses(_bad_credentials_response),
)
async def get_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestFormStrict, Depends()],
) -> OIDCToken:
    """
    Implements the OpenID Connect (OIDC) Resource Owner Password Credentials (ROPC) grant flow.

    Clients can obtain a token set by posting a username and password as form data.
    The response includes `access_token`, `id_token`, `refresh_token`, and related metadata.

    The `access_token` must be included in the `Authorization` header for subsequent
    API requests, e.g.:
        Authorization: Bearer <access_token>

    On the OpenAPI dashboard, you can use the *Authorize* button at the top.
    """
    try:
        token = keycloak.keycloak.basicauth(form_data.username, form_data.password)
        # Add mandatory headers (RFC 6749 §5.1)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Pragma'] = 'no-cache'
        return token

    except KeycloakError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
            headers={'WWW-Authenticate': 'Basic'},
        )


# NOMAD custom token (endpoints and generation functions)


@router.get(
    '/signature_token',
    tags=[APITag.CUSTOM],
    summary='Get a signature token',
)
async def get_signature_token(
    user: Annotated[
        User, Depends(get_current_user(required=True, allow_simple_token=False))
    ],
) -> SignatureToken:
    """
    Generate a signature token for the authenticated user.
    Authentication has to be provided via access token.
    """
    return SignatureToken(
        signature_token=generate_simple_token(user.user_id, expires_in=10)
    )


@router.get(
    '/app_token',
    tags=[APITag.CUSTOM],
    summary='Get an app token',
)
async def get_app_token(
    expires_in: Annotated[
        int, FastApiQuery(gt=0, le=config.services.app_token_max_expires_in)
    ],
    user: Annotated[
        User, Depends(get_current_user(required=True, allow_simple_token=False))
    ],
) -> AppToken:
    """
    Generate an app token with the requested expiration time for the
    authenticated user. Authentication has to be provided via access token.

    This app token can be used like the access token (see `/auth/token`) on subsequent API
    calls to authenticate you using the HTTP header `Authorization: Bearer <app token>`.
    It is provided for user convenience with a user-defined (probably longer) expiration time.
    """
    return AppToken(app_token=generate_simple_token(user.user_id, expires_in))
