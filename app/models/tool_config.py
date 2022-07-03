import logging
import os
from typing import Optional

import botocore
from pydantic import BaseModel

from app.models.jwks import Jwk
from app.models.jwks import JwkStorage
from app.utility import init_logger
from app.utility.aws import Aws

class LTIToolConfig(BaseModel):
    url: str
    learn_app_key: Optional[str] = None
    learn_app_secret: Optional[str] = None

    def jwks_url(self) -> str:
        return f"{self.url}/jwks.json"

    def auth_code_url(self) -> str:
        return f"{self.url}/authcode"

    def base_url(self) -> str:
        return self.url.rstrip("/")

class LTIToolStorage:
    def __init__(self):
        aws = Aws()
        self.ssm_client = aws.ssm

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(LTIToolStorage, cls).__new__(cls)
        return cls.instance

class LTITool:
    def __init__(self, lti_storage: LTIToolStorage):
        init_logger("LTITool")
        self._storage: LTIToolStorage = lti_storage
        self.config = LTIToolConfig(
            url=self.__get_url(),
            learn_app_key=self.__get_learn_app_key(),
            learn_app_secret=self.__get_learn_app_secret(),
        )
        self.jwks = Jwk.all(JwkStorage())

    def set_learn_app_key_and_secret(self, key: str, secret: str):
        self.__set_learn_app_key(key)
        self.__set_learn_app_secret(secret)
        return LTITool(lti_storage=self._storage)

    def tool_kids(self):
        kids = []
        sorted_keys = sorted(self.jwks["keys"], key=lambda x: x["ttl"], reverse=True)
        for key in sorted_keys:
            kids.append(key["kid"])
        return kids

    def __log(self):
        return logging.getLogger("LTIPlatform")

    def __get_url(self):
        return self.__get_secret_value(os.getenv("LTI_TOOLING_API_URL_KEY"), False)

    def __get_learn_app_key(self):
        return self.__get_secret_value(os.getenv("LEARN_APPLICATION_KEY_KEY"), False)

    def __get_learn_app_secret(self):
        return self.__get_secret_value(os.getenv("LEARN_APPLICATION_SECRET_KEY"), True)

    def __set_learn_app_secret(self, secret: str):
        self.__set_secret_value(os.getenv("LEARN_APPLICATION_SECRET_KEY"), secret, True)

    def __set_learn_app_key(self, key: str):
        self.__set_secret_value(os.getenv("LEARN_APPLICATION_KEY_KEY"), key, False)

    def __get_secret_value(self, secret_name: str, with_encryption: bool) -> str:
        try:
            response = self._storage.ssm_client.get_parameter(
                Name=secret_name, WithDecryption=with_encryption
            )
            if response and "Parameter" in response and "Value" in response["Parameter"]:
                return response["Parameter"]["Value"]
            else:
                raise Exception("InvalidParameterException")
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] == "ParameterNotFound":
                self.__log().warning(f"{secret_name} not found in SSM")
                return None
            else:
                msg = f"Retrieving parameter {secret_name} from SSM. {error}"
                self.__log().error(msg)
                raise Exception(msg)

    def __set_secret_value(self, secret_name: str, secret: str, with_encryption: bool):
        try:
            self._storage.ssm_client.put_parameter(
                Name=secret_name,
                Type="SecureString" if with_encryption == True else "String",
                Overwrite=True,
                Value=secret,
            )
        except botocore.exceptions.ClientError as error:
            msg = f"Saving parameter {secret_name} to SSM. {error}"
            self.__log().error()
            raise Exception(msg)
            