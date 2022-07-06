import datetime
import logging
import secrets
from calendar import timegm
from enum import Enum
from enum import auto

import requests

from app.models.jwt import LTIJwtPayload
from app.models.platform_config import LTIPlatform
from app.models.tool_config import LTITool
from app.models.tool_config import LTIToolStorage
from app.utility import init_logger

lti_scopes = (
    "https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly "
    + "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem "
    + "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem.readonly "
    + "https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly "
    + "https://purl.imsglobal.org/spec/lti-ags/scope/score"
)


class GrantType(Enum):
    CLIENT_CREDENTIALS = auto()
    AUTH_CODE = auto()


class TokenClient:
    def __init__(self, **kwargs):
        init_logger("TokenClient")

    @staticmethod
    def request_bearer_token(
        platform: LTIPlatform, grantType: GrantType, tool: LTITool
    ) -> str:

        logging.debug(f"GrantType: {grantType}")
        access_token: str

        if grantType == GrantType.CLIENT_CREDENTIALS:
            access_token = TokenClient.__request_bearer_client_credential(
                platform=platform, tool=tool
            )
        elif grantType == GrantType.AUTH_CODE:
            access_token = TokenClient.__request_bearer_auth_code(platform=platform)

        return access_token

    @staticmethod
    def get_learn_access_token(learn_url, redirect_url, auth_code):
        oauth_url = (
            learn_url
            + "/learn/api/public/v1/oauth2/token?code="
            + auth_code
            + "&redirect_uri="
            + redirect_url
        )

        # Authenticate
        payload = {"grant_type": "authorization_code"}
        lti_tool = LTITool(LTIToolStorage())
        r = requests.post(
            oauth_url,
            data=payload,
            auth=(lti_tool.config.learn_app_key, lti_tool.config.learn_app_secret),
        )

        if not r.ok:
            msg = f"Error retrieving access token from platfom {oauth_url}. {r.reason}: {r.text}"
            logging.error(msg)
            raise Exception(msg)

        # access token (bearer token) to be used to communicate with the Learn REST APIs
        learn_rest_token = r.json()["access_token"]
        return learn_rest_token

    @staticmethod
    def __request_bearer_client_credential(platform: LTIPlatform, tool: LTITool) -> str:
        """
        Generate JWT and then request client credential grant access token.
        Tool Originating Messages: Client Credential grant:
        https://www.imsglobal.org/spec/security/v1p0/#tool-originating-messages
        https://www.imsglobal.org/spec/security/v1p0/#using-json-web-tokens-with-oauth-2-0-client-credentials-grant
        https://www.oauth.com/oauth2-servers/access-tokens/client-credentials/
        """
        jwt = LTIJwtPayload()
        time_now = datetime.datetime.now(tz=datetime.timezone.utc)

        # TODO: get timeout seconds from jwt.py
        payload = dict(
            aud=platform.config.auth_token_url,
            exp=timegm(
                (time_now + datetime.timedelta(seconds=int(300))).utctimetuple()
            ),
            jti=secrets.token_hex(16),
            iat=timegm(time_now.utctimetuple()),
            iss=platform.config.client_id,
            sub=platform.config.client_id,
        )

        jwtstring = jwt.encode(payload=payload, tool=tool)

        auth_request = {
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": jwtstring,
            "scope": lti_scopes,
        }

        r = requests.post(platform.config.auth_token_url, data=auth_request)
        if not r.ok:
            msg = f"Error retrieving access token from platform {platform.config.auth_token_url}. {r.reason}: {r.text}"
            logging.error(msg)
            raise Exception(msg)

        # access token (bearer token) to be used to communicate with the Provider (LMS)
        access_token = r.json()["access_token"]
        return access_token

    def __request_bearer_auth_code(self) -> str:
        pass
