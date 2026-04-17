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

import urllib
from collections.abc import Callable, Collection
from enum import Enum
from inspect import Parameter, Signature
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi import Query as FastApiQuery
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestFormStrict

from nomad import datamodel
from nomad.auth.keycloak import KeycloakError, OIDCToken, keycloak
from nomad.auth.scopes import Scope
from nomad.auth.tokens import (
    AppToken,
    AuthResult,
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


# Authentication (resolve user) and authorization (enforce scopes)


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f'{root_path}/auth/token', auto_error=False
)


def _resolve_user_with_scopes(
    *,
    required_scopes: set[str],
    allow_anonymous: bool,
    request: Request | None = None,
    keycloak_token: str | None = None,
    simple_token: str | None = None,
    upload_token: str | None = None,
) -> User | None:
    """Resolve User/scopes from token and validate."""
    # Resolve user and extract scopes from (simple->keycloak->upload) token
    auth_result: AuthResult | None = None

    # Resolve user from simple token
    if auth_result is None and simple_token:
        try:
            unverified_payload = jwt.decode(
                simple_token, options={'verify_signature': False}
            )
            # This is used to distinguish simple token from keycloak token:
            # simple token only has `user/exp` in payload,
            # while the keycloak has much more (RFC 7519)
            if unverified_payload.keys() == {'user', 'exp'}:
                auth_result = get_user_from_simple_token(simple_token)
        except jwt.DecodeError as e:  # token could be non-JWT (for testing)
            logger.error('Failed to decode simple token', exc_info=e)

    # Resolve user from keycloak token (cookie or header)
    if auth_result is None and (keycloak_token or request):
        # Get token from cookie
        if keycloak_token is None and request is not None:
            auth_cookie = request.cookies.get('Authorization')
            if auth_cookie is not None:
                auth_cookie = urllib.parse.unquote(auth_cookie)
                keycloak_token = auth_cookie.removeprefix('Bearer ')

        if keycloak_token is not None:
            auth_result = get_user_from_keycloak_token(keycloak_token)

    # Resolve user from upload token
    if auth_result is None and upload_token:
        auth_result = get_user_from_upload_token(upload_token)

    if auth_result is None:  # user resolving failed: anonymous user
        user = None
        scopes = config.auth.unauthenticated_user_scopes_resolved
    else:
        user = auth_result.user
        scopes = auth_result.scopes

    # [DEV ONLY] allow tester to bypass auth
    if config.tests.assume_auth_for_username:
        if config.services.mode != ModeEnum.DEVELOPMENT:
            raise ValueError('assume_auth_for_username is development-only')

        user = datamodel.User.get(username=config.tests.assume_auth_for_username)
        scopes = Scope.all_values()  # full permission for tester

    # Anonymous users
    if user is None:
        if not allow_anonymous or config.auth.require_authentication:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Authentication required.',
                headers={'WWW-Authenticate': 'Bearer'},
            )

    # Non-anonymous user
    else:
        # Validate user against Keycloak
        try:
            if datamodel.User.get(user.user_id) is None:
                raise ValueError('User not found in database')
        except Exception as e:
            logger.error('API usage by unknown user.', exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You are logged in with an unknown user',
            ) from e

        # Check user whitelist (via `authorized_users`)
        if (
            config.auth.authorized_users is not None
            and user.email not in config.auth.authorized_users
            and user.username not in config.auth.authorized_users
        ):
            if config.auth.reject_unauthorized_users:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail='You are not authorized to access this Oasis',
                )
            else:
                scopes = config.auth.unauthorized_user_scopes_resolved

    # Enforce backend scopes
    if missing_scopes := required_scopes - set(scopes):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f'Missing scopes: {sorted(missing_scopes)}',
        )

    return user

def _resolve_user(
    *,
    required: bool = False,
    request: Request | None = None,
    keycloak_token: str | None = None,
    simple_token: str | None = None,
    upload_token: str | None = None,
    upload_token_query_param: str | None = None,
) -> User | None:
    """
    Backwards-compatible wrapper expected by nomad.app.main.
    """
    if upload_token_query_param is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Passing upload token via query parameter 'token' is no longer supported. "
                "Please use the 'Upload-Token' header instead."
            ),
        )

    return _resolve_user_with_scopes(
        required_scopes=set(),
        allow_anonymous=not required,
        request=request,
        keycloak_token=keycloak_token,
        simple_token=simple_token,
        upload_token=upload_token,
    )

def get_current_user(
    required_scopes: Collection[str] | str,
    *,
    allow_anonymous: bool = True,
    allow_keycloak_token: bool = True,
    allow_simple_token: bool = True,
    allow_upload_token: bool = False,
) -> Callable:
    """
    Build a FastAPI dependency that resolves User and enforces scopes.

    Args:
        required_scopes: scope(s) this endpoint needs.
        allow_anonymous: whether to allow anonymous (no-login) access.
        allow_*_token: toggle which tokens are accepted.
    """
    if isinstance(required_scopes, str):
        required_scopes = {required_scopes}
    else:
        required_scopes = set(required_scopes)

    def current_user(**kwargs) -> User | None:
        return _resolve_user_with_scopes(
            required_scopes=required_scopes,
            allow_anonymous=allow_anonymous,
            request=kwargs.get('request'),
            keycloak_token=kwargs.get('keycloak_token'),
            simple_token=kwargs.get('simple_token'),
            upload_token=kwargs.get('upload_token'),
        )

    # Build signature
    parameters: list[Parameter] = []

    if allow_keycloak_token:
        parameters.append(
            Parameter(
                name='request',
                annotation=Request,  # for getting keycloak token from cookie
                kind=Parameter.POSITIONAL_OR_KEYWORD,
            )
        )
        parameters.append(
            Parameter(
                name='keycloak_token',
                annotation=str | None,
                default=Depends(oauth2_scheme),
                kind=Parameter.KEYWORD_ONLY,
            )
        )

    if allow_simple_token:
        parameters.append(
            Parameter(
                name='simple_token',
                annotation=str | None,
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
        token = keycloak.basicauth(form_data.username, form_data.password)
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
        User,
        Depends(get_current_user([Scope.TOKENS_CREATE], allow_anonymous=False)),
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
        User,
        Depends(get_current_user([Scope.TOKENS_CREATE], allow_anonymous=False)),
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
