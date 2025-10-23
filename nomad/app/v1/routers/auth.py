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

import datetime
import hashlib
import hmac
import uuid
from collections.abc import Callable
from enum import Enum
from inspect import Parameter, Signature
from typing import Literal, cast

import jwt
import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi import Query as FastApiQuery
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from nomad import datamodel, infrastructure, utils
from nomad._auth import check_api_secret
from nomad.config import config
from nomad.config.models.config import ModeEnum
from nomad.utils import get_logger, strip

from ..common import root_path
from ..models import HTTPExceptionModel, User
from ..utils import create_responses

logger = get_logger(__name__)

router = APIRouter()


class APITag(str, Enum):
    DEFAULT = 'auth'


class Token(BaseModel):
    access_token: str
    token_type: Literal['bearer']


class SignatureToken(BaseModel):
    signature_token: str


class AppToken(BaseModel):
    app_token: str


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f'{root_path}/auth/token', auto_error=False
)


def resolve_user(
    *,
    request: Request | None = None,
    bearer_token: str | None = None,
    upload_token: str | None = None,
    upload_token_query_param: str | None = None,
    signature_token: str | None = None,
    required: bool = False,
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
    if user is None and bearer_token:
        user = _get_user_from_bearer_token(bearer_token)
    if user is None and upload_token:
        user = _get_user_from_upload_token(upload_token)
    # `_get_user_signature_token_auth` would also handle token in cookie
    if user is None and (signature_token or request):
        user = _get_user_from_signature_token(signature_token, request)

    if user is None and config.tests.assume_auth_for_username:
        if config.services.mode == ModeEnum.PRODUCTION:
            raise ValueError(
                'assume_auth_for_username is test-only and not allowed in production mode'
            )
        user = datamodel.User.get(username=config.tests.assume_auth_for_username)

    # Check if token is available
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


def create_user_dependency(
    required: bool = False,
    bearer_token_auth_allowed: bool = True,
    upload_token_auth_allowed: bool = False,
    signature_token_auth_allowed: bool = False,
) -> Callable:
    """
    Creates a dependency for getting the authenticated user. The parameters define if
    the authentication is required or not, and which authentication methods are allowed.
    """

    def user_dependency(**kwargs) -> User | None:
        # We don't need to check token allowed flags here as
        # `fastapi` would only inject based on signature
        return resolve_user(
            request=kwargs.get('request'),
            bearer_token=kwargs.get('bearer_token'),
            upload_token=kwargs.get('upload_token'),
            upload_token_query_param=kwargs.get('upload_token_query_param'),
            signature_token=kwargs.get('signature_token'),
            required=required,
        )

    # Create the desired function signature (as it depends on which auth options are allowed)
    parameters: list[Parameter] = []
    if bearer_token_auth_allowed:
        parameters.append(
            Parameter(
                name='bearer_token',
                annotation=str,
                default=Depends(oauth2_scheme),
                kind=Parameter.KEYWORD_ONLY,
            )
        )
    if upload_token_auth_allowed:
        parameters.append(
            Parameter(
                name='upload_token',
                annotation=str,
                default=Header(
                    None,
                    alias='Upload-Token',
                    description='Token for simplified authentication for uploading.',
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
    if signature_token_auth_allowed:
        parameters.append(
            Parameter(
                name='signature_token',
                annotation=str,
                default=FastApiQuery(
                    None, description='Signature token used to sign download urls.'
                ),
                kind=Parameter.KEYWORD_ONLY,
            )
        )
        parameters.append(
            Parameter(name='request', annotation=Request, kind=Parameter.KEYWORD_ONLY)
        )

    user_dependency.__signature__ = Signature(parameters)  # type: ignore[attr-defined]
    return user_dependency


def _get_user_from_bearer_token(bearer_token: str | None) -> User | None:
    """
    Verifies bearer_token (throwing HTTPException if illegal value provided).

    Returns:
        The corresponding User object,
        or None if no token provided.
    """
    if bearer_token in {None, 'undefined'}:
        return None

    try:
        unverified_payload = jwt.decode(
            bearer_token, options={'verify_signature': False}
        )
        if unverified_payload.keys() == {'user', 'exp'}:
            return _get_user_from_simple_token(bearer_token)
    except jwt.DecodeError as e:  # token could be non-JWT, e.g. for testing
        logger.error('Failed to decode JWT', exc_info=e)

    try:
        return cast(datamodel.User, infrastructure.keycloak.tokenauth(bearer_token))
    except infrastructure.KeycloakError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={'WWW-Authenticate': 'Bearer'},
        )


def _get_user_from_signature_token(
    signature_token: str | None, request: Request | None
) -> User | None:
    """
    Verifies the signature token (throwing HTTPException if illegal value provided).

    NOTE: it would also handle token in cookie

    Returns:
        The corresponding User object,
        or None if no signature_token provided.
    """
    if signature_token is not None:
        return _get_user_from_simple_token(signature_token)

    if request is not None:
        auth_cookie = request.cookies.get('Authorization')
        if auth_cookie is not None:
            try:
                auth_cookie = requests.utils.unquote(auth_cookie)
                cookie_bearer_token = auth_cookie.removeprefix('Bearer ')
                return cast(
                    datamodel.User,
                    infrastructure.keycloak.tokenauth(cookie_bearer_token),
                )

            except infrastructure.KeycloakError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(e),
                    headers={'WWW-Authenticate': 'Bearer'},
                )
            except Exception as e:
                logger.error('Failed to process token from cookie', exc_info=e)

    return None


def _get_user_from_simple_token(token: str | None) -> User | None:
    """
    Verifies a simple token (throwing HTTPException if illegal value provided).

    Returns:
        The corresponding user object,
        or None if no token was provided.
    """
    if token is None:
        return None

    check_api_secret()

    try:
        decoded = jwt.decode(token, config.services.api_secret, algorithms=['HS256'])
        return datamodel.User.get(user_id=decoded['user'])

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token with invalid/unexpected payload.',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Expired token.',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid token.',
            headers={'WWW-Authenticate': 'Bearer'},
        )


def _get_user_from_upload_token(upload_token: str | None) -> User | None:
    """
    Verifies the upload token (throwing HTTPException if illegal value provided).

    Returns:
        The corresponding User object,
        or None if no upload_token provided.
    """
    if upload_token is None:
        return None

    check_api_secret()

    try:
        payload, signature = upload_token.split('.', 1)
        payload_bytes = utils.base64_decode(payload)
        signature_bytes = utils.base64_decode(signature)

        expected = hmac.new(
            config.services.api_secret.encode('utf-8'),
            msg=payload_bytes,
            digestmod=hashlib.sha256,
        )

        if not hmac.compare_digest(signature_bytes, expected.digest()):
            raise ValueError('Invalid HMAC signature')

        user_id = str(uuid.UUID(bytes=payload_bytes))
        return cast(datamodel.User, infrastructure.user_management.get_user(user_id))

    except Exception:
        # Decode error, format error, user not found, etc.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='An invalid upload token was supplied.',
            headers={'WWW-Authenticate': 'Bearer'},
        )


_bad_credentials_response = (
    status.HTTP_401_UNAUTHORIZED,
    {
        'model': HTTPExceptionModel,
        'description': strip(
            """
        Unauthorized. The provided credentials were not recognized."""
        ),
    },
)


@router.post(
    '/token',
    tags=[APITag.DEFAULT],
    summary='Get an access token',
    responses=create_responses(_bad_credentials_response),
    response_model=Token,
)
async def get_token(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """
    This API uses OAuth as an authentication mechanism. This operation allows you to
    retrieve an *access token* by posting username and password as form data.

    This token can be used on subsequent API calls to authenticate
    you. Operations that support or require authentication will expect the *access token*
    in an HTTP Authorization header like this: `Authorization: Bearer <access token>`.

    On the OpenAPI dashboard, you can use the *Authorize* button at the top.

    You only need to provide `username` and `password` values. You can ignore the other
    parameters.
    """
    try:
        access_token = infrastructure.keycloak.basicauth(
            form_data.username, form_data.password
        )
    except infrastructure.KeycloakError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
            headers={'WWW-Authenticate': 'Basic'},
        )

    return Token(access_token=access_token, token_type='bearer')


@router.get(
    '/signature_token',
    tags=[APITag.DEFAULT],
    summary='Get a signature token',
    response_model=SignatureToken,
)
async def get_signature_token(
    user: User | None = Depends(create_user_dependency(required=True)),
) -> SignatureToken:
    """
    Generate a signature token for the authenticated user.
    Authentication has to be provided via access token.
    """
    return SignatureToken(
        signature_token=_generate_simple_token(user.user_id, expires_in=10)
    )


@router.get(
    '/app_token',
    tags=[APITag.DEFAULT],
    summary='Get an app token',
    response_model=AppToken,
)
async def get_app_token(
    expires_in: int = FastApiQuery(gt=0, le=config.services.app_token_max_expires_in),
    user: User = Depends(create_user_dependency(required=True)),
) -> AppToken:
    """
    Generate an app token with the requested expiration time for the
    authenticated user. Authentication has to be provided via access token.

    This app token can be used like the access token (see `/auth/token`) on subsequent API
    calls to authenticate you using the HTTP header `Authorization: Bearer <app token>`.
    It is provided for user convenience with a user-defined (probably longer) expiration time.
    """
    return AppToken(app_token=_generate_simple_token(user.user_id, expires_in))


def _generate_simple_token(user_id: str, expires_in: float) -> str:
    """
    Generate a simple token: JWT encoded user_id and expiration time,
    signed with the API secret.
    """
    check_api_secret()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=expires_in
    )
    payload = dict(user=user_id, exp=expires_at)
    return jwt.encode(payload, config.services.api_secret, 'HS256')


def _generate_upload_token(user: User) -> str:
    """Generate an upload token for user."""
    check_api_secret()
    payload = uuid.UUID(user.user_id).bytes
    signature = hmac.new(
        config.services.api_secret.encode('utf-8'),
        msg=payload,
        digestmod=hashlib.sha256,
    )

    return f'{utils.base64_encode(payload)}.{utils.base64_encode(signature.digest())}'
