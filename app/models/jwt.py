import base64
import json
import logging
import os
from typing import Optional

import jwt
from jwt import PyJWKClient
from jwt import algorithms
from pydantic import BaseModel

from app.models.platform_config import LTIPlatform
from app.models.tool_config import LTITool
from app.utility import init_logger
from app.utility.aws import Aws


class LTIJwtPayload(BaseModel):
    token: Optional[str] = None
    header: Optional[dict] = None
    payload: Optional[dict] = None
    aud: Optional[str] = None
    context_id: Optional[str] = None
    context_title: Optional[str] = None
    deep_linking_settings_data: Optional[str] = None
    deep_linking_settings_return_url: Optional[str] = None
    deployment_id: Optional[str] = None
    endpoint_lineitem: Optional[str] = None
    endpoint_lineitems: Optional[str] = None
    scopes: Optional[str] = None
    iss: Optional[str] = None
    message_type: Optional[str] = None
    nonce: Optional[str] = None
    one_time_session_token: Optional[str] = None
    platform_product_code: Optional[str] = None
    platform_url: Optional[str] = None
    sub: Optional[str] = None
    ttl: Optional[int] = 0

    def __init__(self, token: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        init_logger("LTIJwtPayload")
        self.__log().debug(
            f"Default algorithms {algorithms.get_default_algorithms().keys()}"
        )
        self.ttl = 300  # expire token after 5 minutes

        # If token provided through constructor, parse without verification and hydrate class properties
        if token is not None:
            self.__log().debug(f"token: {token}")
            if len(token.split(".")) != 3:
                raise Exception("InvalidParameterException")

            # parse the token without verification so we can access the properties
            header = jwt.get_unverified_header(token)
            payload = jwt.decode(token, options={"verify_signature": False})

            self.token = token
            self.header = header
            self.payload = payload
            self.aud = self.__get_aud(payload)
            self.context_id = (
                payload["https://purl.imsglobal.org/spec/lti/claim/context"]["id"]
                if "https://purl.imsglobal.org/spec/lti/claim/context" in payload
                else ""
            )
            self.context_title = (
                payload["https://purl.imsglobal.org/spec/lti/claim/context"]["title"]
                if "https://purl.imsglobal.org/spec/lti/claim/context" in payload
                else ""
            )
            # https://www.imsglobal.org/spec/lti-dl/v2p0#deep-linking-request-message
            self.deep_linking_settings_data = (
                payload[
                    "https://purl.imsglobal.org/spec/lti-dl/claim/deep_linking_settings"
                ]["data"]
                if "https://purl.imsglobal.org/spec/lti-dl/claim/deep_linking_settings"
                in payload
                else ""
            )
            self.deep_linking_settings_return_url = (
                payload[
                    "https://purl.imsglobal.org/spec/lti-dl/claim/deep_linking_settings"
                ]["deep_link_return_url"]
                if "https://purl.imsglobal.org/spec/lti-dl/claim/deep_linking_settings"
                in payload
                else ""
            )
            self.deployment_id = (
                payload["https://purl.imsglobal.org/spec/lti/claim/deployment_id"]
                if "https://purl.imsglobal.org/spec/lti/claim/deployment_id" in payload
                else ""
            )
            # https://www.imsglobal.org/spec/lti-ags/v2p0/
            self.endpoint_lineitem = (
                payload["https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"][
                    "lineitem"
                ]
                if "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint" in payload
                and "lineitem"
                in payload["https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"]
                else ""
            )
            self.endpoint_lineitems = (
                payload["https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"][
                    "lineitems"
                ]
                if "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint" in payload
                and "lineitems"
                in payload["https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"]
                else ""
            )
            self.scopes = (
                payload["https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"][
                    "scopes"
                ]
                if "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint" in payload
                and "scopes"
                in payload["https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"]
                else ""
            )
            self.iss = payload["iss"]
            self.message_type = (
                payload["https://purl.imsglobal.org/spec/lti/claim/message_type"]
                if "https://purl.imsglobal.org/spec/lti/claim/message_type" in payload
                else ""
            )
            self.nonce = payload["nonce"]
            self.one_time_session_token = (
                payload["https://blackboard.com/lti/claim/one_time_use_token"]
                if "https://blackboard.com/lti/claim/one_time_use_token" in payload
                else ""
            )
            self.platform_product_code = (
                payload["https://purl.imsglobal.org/spec/lti/claim/tool_platform"][
                    "product_family_code"
                ]
                if "https://purl.imsglobal.org/spec/lti/claim/tool_platform" in payload
                else ""
            )
            self.platform_url = (
                payload["https://purl.imsglobal.org/spec/lti/claim/tool_platform"][
                    "url"
                ]
                if "https://purl.imsglobal.org/spec/lti/claim/tool_platform" in payload
                else ""
            )
            self.sub = payload["sub"]

        else:
            self.__log().debug("no params")

    def __get_aud(self, payload):
        # TODO : Verify that only the first audience should be leveraged.
        # https://www.imsglobal.org/spec/security/v1p0/#id-token
        if isinstance(payload["aud"], list):
            return payload["aud"][0]
        else:
            return payload["aud"]

    def __bytes_to_urlsafe_base64(self, b):
        return base64.urlsafe_b64encode(b).replace(b"=", b"").decode("utf-8")

    def encode(self, payload: dict, tool: LTITool) -> str:
        """
        Generate and sign a JWT of self.
        Ref: https://www.imsglobal.org/spec/security/v1p0/#tool-originating-messages

        :param payload: the payload to encode
        :param tool: the tool configuration
        :return: encoded jwt string
        """
        header = dict(
            typ="JWT",
            alg="RS256",
            kid=tool.tool_kids()[0],
        )

        json_header = self.__bytes_to_urlsafe_base64(
            json.dumps(header, separators=(",", ":")).encode()
        )
        json_payload = self.__bytes_to_urlsafe_base64(
            json.dumps(payload, separators=(",", ":")).encode()
        )
        aws = Aws()
        kms_client = aws.kms
        kms_key_id = os.getenv("KMS_KEY_ID")
        try:
            kms_response = kms_client.sign(
                KeyId=kms_key_id,
                Message=f"{json_header}.{json_payload}",
                MessageType="RAW",
                SigningAlgorithm="RSASSA_PKCS1_V1_5_SHA_256",
            )

            encoded_signature = self.__bytes_to_urlsafe_base64(
                kms_response["Signature"]
            )

            # If needing the JWK to verify the token, uncomment the following line and paste into jwt.io
            # self.jwks = Jwk.all(JwkStorage())

        except Exception as e:
            msg = f"Failed to sign JWT: {e}"
            self.__log().error(msg)
            raise Exception(msg)

        self.token = f"{json_header}.{json_payload}.{encoded_signature}"
        self.header = header
        self.payload = payload
        self.aud = self.__get_aud(payload)

        if "iss" in payload:
            self.iss = payload["iss"]

        if "sub" in payload:
            self.sub = payload["sub"]

        return self.token

    def verify(self, platform: LTIPlatform):
        """
        Authentication response validation:
        Ref: https://www.imsglobal.org/spec/security/v1p0/#authentication-response-validation

        :param platform: the originating platform (LMS) that is the created the token
        :return: validated JWT self
        """

        # 1 The Tool MUST Validate the signature of the ID Token according to JSON Web Signature [RFC7515], Section 5.2 using the Public Key from the Platform;
        # 2 The Issuer Identifier for the Platform MUST exactly match the value of the iss (Issuer) Claim (therefore the Tool MUST previously have been made aware of this identifier);
        # 3 The Tool MUST validate that the aud (audience) Claim contains its client_id value registered as an audience with the Issuer identified by the iss (Issuer) Claim. The aud (audience) Claim MAY contain an array with more than one element. The Tool MUST reject the ID Token if it does not list the client_id as a valid audience, or if it contains additional audiences not trusted by the Tool. The request message will be rejected with a HTTP code of 401;
        # load the jwks and find the signing key via the key_set_url stored in Config (do not trust the token provided)

        jwks_client = PyJWKClient(platform.config.key_set_url)
        signing_key = jwks_client.get_signing_key_from_jwt(self.token)

        # decode (verify) the token, will throw and Exception on validation error
        valid = jwt.decode(
            self.token,
            signing_key.key,
            issuer=platform.config.iss,
            audience=platform.config.client_id,
            algorithms=[self.header["alg"]],
        )
        # 4 If the ID Token contains multiple audiences, the Tool SHOULD verify that an azp Claim is present;
        if isinstance(valid["aud"], list):
            if "azp" not in valid:
                raise Exception("Authorized Party not provided")
        # 5 If an azp (authorized party) Claim is present, the Tool SHOULD verify that its client_id is the Claim's value;
        if "azp" in valid:
            if valid["azp"] != platform.config.client_id:
                raise Exception("Invalid Authorized Party")
        # 6 The ID Token MUST contain a nonce Claim. The Tool SHOULD verify that it has not yet received this nonce value (within a Tool-defined time window), in order to help prevent replay attacks. The Tool MAY define its own precise method for detecting replay attacks.
        if "nonce" not in valid:
            raise Exception("Nonce not provided")

        return self

    def __log(self):
        return logging.getLogger("LTIJwtPayload")
