import json
import logging
import os
from typing import Optional

import botocore
from boto3.dynamodb.types import TypeDeserializer
from boto3.dynamodb.types import TypeSerializer
from pydantic import BaseModel

from app.utility import init_logger
from app.utility.aws import Aws


class LTIPlatformConfig(BaseModel):
    PK: str
    auth_token_url: str
    auth_login_url: str
    client_id: str
    lti_deployment_id: str
    iss: str
    key_set_url: str
    learn_application_key: Optional[str] = None
    learn_application_secret: Optional[str] = None


class LTIPlatformStorage:
    def __init__(self):
        self.TABLE_NAME = os.getenv("TABLE_NAME")
        aws = Aws()
        self.ddbclient = aws.dynamodb

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(LTIPlatformStorage, cls).__new__(cls)
        return cls.instance


class LTIPlatform:
    def __init__(
        self,
        lti_storage: LTIPlatformStorage,
        config: Optional[LTIPlatformConfig] = None,
    ):
        init_logger("LTIPlatform")
        self._storage: LTIPlatformStorage = lti_storage
        self.config = LTIPlatformConfig(
            auth_token_url=config.auth_token_url if config is not None else "",
            auth_login_url=config.auth_login_url if config is not None else "",
            client_id=config.client_id if config is not None else "",
            lti_deployment_id=config.lti_deployment_id if config is not None else "",
            iss=config.iss if config is not None else "",
            key_set_url=config.key_set_url if config is not None else "",
            PK="",
        )

    def __log(self):
        return logging.getLogger("LTIPlatform")

    def load(self, client_id: str, iss: str, lti_deployment_id: Optional[str]):
        response = self._storage.ddbclient.get_item(
            TableName=self._storage.TABLE_NAME,
            Key={"PK": {"S": f"CONFIG#{client_id}#{iss}#{lti_deployment_id}"}},
        )
        if "Item" in response is not None:
            deserializer = TypeDeserializer()
            record = deserializer.deserialize({"M": response["Item"]})
            self.config = LTIPlatformConfig(**record)
        else:
            msg = f"No PlatformConfig record found for CONFIG#{client_id}#{iss}#{lti_deployment_id}."
            self.__log().warning(msg)
            raise Exception(msg)
        return self

    def save(self):
        if (
            self.config is None
            or self.config.auth_token_url is None
            or self.config.auth_login_url is None
            or self.config.client_id is None
            or self.config.iss is None
            or self.config.key_set_url is None
        ):
            raise Exception("InvalidParameterException")

        self.config.PK = f"CONFIG#{self.config.client_id}#{self.config.iss}#{self.config.lti_deployment_id}"
        try:
            serializer = TypeSerializer()
            item = serializer.serialize(self.config.dict())["M"]
            self._storage.ddbclient.put_item(TableName=self._storage.TABLE_NAME, Item=item)
        except botocore.exceptions.ClientError as error:
            msg = f"Error persisting PlatformConfig for {self.config.PK}. {json.dumps(error)}"
            self.__log().error(msg)
            raise Exception(msg)
        return self
