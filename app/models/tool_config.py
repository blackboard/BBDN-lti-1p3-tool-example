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

    def __log(self):
        return logging.getLogger("LTIPlatform")

    def __get_url(self):
        try:
            response = self._storage.ssm_client.get_parameter(Name=os.getenv("LTI_TOOLING_API_URL_KEY"))
            if response and "Parameter" in response and "Value" in response["Parameter"]:
                return response["Parameter"]["Value"]
            else:
                raise Exception("InvalidParameterException")
        except botocore.exceptions.ClientError as error:
            msg = f"Retrieving parameter {os.getenv('lti_tooling_api_url_key')} from SSM. {error}"
            self.__log().error()
            raise Exception(msg)

    def __get_learn_app_key(self):
        try:
            response = self._storage.ssm_client.get_parameter(Name=os.getenv("LEARN_APPLICATION_KEY_KEY"))
            if response and "Parameter" in response and "Value" in response["Parameter"]:
                return response["Parameter"]["Value"]
            else:
                raise Exception("InvalidParameterException")
        except botocore.exceptions.ClientError as error:
            if "ParameterNotFound" == error.response["Error"]["Code"]:
                self.__log().warning(f"{os.getenv('LEARN_APPLICATION_KEY_KEY')} not found in SSM")
                return None
            else:
                msg = f"Retrieving parameter {os.getenv('LEARN_APPLICATION_KEY_KEY')} from SSM. {error}"
                self.__log().error(msg)
                raise Exception(msg)

    def __get_learn_app_secret(self):
        try:
            response = self._storage.ssm_client.get_parameter(
                Name=os.getenv("LEARN_APPLICATION_SECRET_KEY"), WithDecryption=True
            )
            if response and "Parameter" in response and "Value" in response["Parameter"]:
                return response["Parameter"]["Value"]
            else:
                raise Exception("InvalidParameterException")
        except botocore.exceptions.ClientError as error:
            if "ParameterNotFound" == error.response["Error"]["Code"]:
                self.__log().warning(f"{os.getenv('LEARN_APPLICATION_SECRET_KEY')} not found in SSM")
                return None
            else:
                msg = f"Retrieving parameter {os.getenv('LEARN_APPLICATION_SECRET_KEY')} from SSM. {error}"
                self.__log().error(msg)
                raise Exception(msg)

    def set_learn_app_key_and_secret(self, key: str, secret: str):
        self.__set_learn_app_key(key)
        self.__set_learn_app_secret(secret)
        return LTITool(lti_storage=self._storage)

    def __set_learn_app_secret(self, secret: str):
        try:
            self._storage.ssm_client.put_parameter(
                Name=os.getenv("LEARN_APPLICATION_SECRET_KEY"),
                Type="SecureString",
                Overwrite=True,
                Value=secret,
            )

        except botocore.exceptions.ClientError as error:
            msg = f"Saving parameter {os.getenv('LEARN_APPLICATION_SECRET_KEY')} to SSM. {error}"
            self.__log().error()
            raise Exception(msg)

    def __set_learn_app_key(self, key: str):
        try:
            self._storage.ssm_client.put_parameter(
                Name=os.getenv("LEARN_APPLICATION_KEY_KEY"),
                Type="String",
                Overwrite=True,
                Value=key,
            )

        except botocore.exceptions.ClientError as error:
            msg = f"Saving parameter {os.getenv('LEARN_APPLICATION_KEY_KEY')} to SSM. {error}"
            self.__log().error()
            raise Exception(msg)

    def tool_kids(self):
        kids = []
        sorted_keys = sorted(self.jwks["keys"], key=lambda x: x["ttl"], reverse=True)
        for key in sorted_keys:
            kids.append(key["kid"])
        return kids
