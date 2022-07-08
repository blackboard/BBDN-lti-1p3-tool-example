import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

import boto3
import botocore
from boto3.dynamodb.types import TypeDeserializer
from boto3.dynamodb.types import TypeSerializer
from pydantic import BaseModel

from app.utility import init_logger
from app.utility.cryptography_client import CryptographyClient


class LTIStateRecord(BaseModel):
    PK: str = ""
    id: str = str(uuid.uuid4())
    nonce: str = str(uuid.uuid4())
    nonce_count: int = 0
    ttl: int = 0
    data: Optional[dict] = None
    platform_lti_token: Optional[str] = None
    id_token: str = ""
    learn_rest_token: Optional[str] = None

    def get_platform_lti_token(self):
        try:
            return CryptographyClient.decrypt_string(self.platform_lti_token)
        except Exception as e:
            logging.error(f"Error decrypting platform LTI token: {e}")
            raise e

    def set_platform_lti_token(self, new_platform_lti_token):
        try:
            self.platform_lti_token = CryptographyClient.encrypt_string(new_platform_lti_token)
        except Exception as e:
            logging.error(f"Error encrypting platform LTI token: {e}")
            raise e

    def get_platform_learn_rest_token(self):
        try:
            return CryptographyClient.decrypt_string(self.learn_rest_token)
        except Exception as e:
            logging.error(f"Error decrypting platform Learn REST token: {e}")
            raise e

    def set_platform_learn_rest_token(self, new_learn_rest_token):
        try:
            self.learn_rest_token = CryptographyClient.encrypt_string(new_learn_rest_token)
        except Exception as e:
            logging.error(f"Error encrypting platform Learn REST token: {e}")
            raise e


class LTIStateStorage:
    def __init__(self):
        self.TABLE_NAME = os.getenv("TABLE_NAME")
        self.TTL = os.getenv("STATE_TTL", "7200")
        self.ddbclient = boto3.client("dynamodb")

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(LTIStateStorage, cls).__new__(cls)
        return cls.instance


class LTIState:
    def __init__(self, lti_storage: LTIStateStorage):
        init_logger("LTIState")
        self._storage: LTIStateStorage = lti_storage
        self.record = LTIStateRecord()

    def validate(self, nonce: str):
        if self.record.id is None or nonce is None:
            self.__log().error(f"id={self.record.id},nonce={nonce}")
            raise Exception("InvalidParameterException")

        if self.record.nonce != nonce and self.record.nonce_count != 0:
            self.__log().warning("Invalid state")
            return False
        else:
            try:
                self._storage.ddbclient.update_item(
                    TableName=self._storage.TABLE_NAME,
                    Key={"PK": {"S": f"STATE#{self.record.id}"}},
                    UpdateExpression="ADD nonce_count :inc",
                    ConditionExpression="nonce = :nonce AND nonce_count = :nonce_count",
                    ExpressionAttributeValues={
                        ":inc": {"N": "1"},
                        ":nonce": {"S": self.record.nonce},
                        ":nonce_count": {"N": "0"},
                    },
                )
                return True
            except botocore.exceptions.ClientError as error:
                msg = f"Error persisting State record for STATE#{self.record.id}. {json.dumps(error)}"
                self.__log().error(msg)
                raise Exception(msg)

    def __log(self):
        return logging.getLogger("LTIPlatform")

    def load(self, id: str):
        try:
            response = self._storage.ddbclient.get_item(
                TableName=self._storage.TABLE_NAME,
                Key={"PK": {"S": f"STATE#{id}"}},
            )
            if "Item" in response:
                deserializer = TypeDeserializer()
                r = deserializer.deserialize({"M": response["Item"]})
                self.record = LTIStateRecord(**r)

            else:
                self.__log().warning(f"No State record found for STATE#{id}.")

            return self
        except botocore.exceptions.ClientError as error:
            msg = f"Error retrieving State for STATE#{self.id()}. {json.dumps(error)}"
            self.__log().error(msg)
            raise Exception(msg)

    def save(self):
        self.record.PK = f"STATE#{self.record.id}"
        self.record.ttl = int(datetime.now().timestamp()) + int(
            self._storage.TTL
        )  # this will auto expire the state in DDB

        try:
            serializer = TypeSerializer()
            item = serializer.serialize(self.record.dict())["M"]
            self._storage.ddbclient.put_item(TableName=self._storage.TABLE_NAME, Item=item)
        except botocore.exceptions.ClientError as error:
            msg = f"Error persisting State for {self.record.PK}. {json.dumps(error)}"
            self.__log().error(msg)
            raise Exception(msg)
        return self
