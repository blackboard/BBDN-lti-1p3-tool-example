import base64
import json
import logging
import os
import uuid
from datetime import datetime

import botocore
from boto3.dynamodb.conditions import Attr
from boto3.dynamodb.types import TypeDeserializer
from boto3.dynamodb.types import TypeSerializer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_der_public_key
from jwcrypto.jwk import JWK
from pydantic import BaseModel

from app.utility import init_logger
from app.utility.aws import Aws


class JwkRecord(BaseModel):
    PK: str = ""
    kid: str = ""
    kms_key_id: str
    public_key_pem: str
    ttl: int = 0
    _jwks = JWK()

    def _to_jwk(self):
        self._jwks.import_from_pem(data=base64.b64decode(self.public_key_pem), kid=self.kid)
        return self._jwks


class JwkStorage:
    def __init__(self):
        self.TABLE_NAME = os.getenv("TABLE_NAME")
        self.TTL = os.getenv("JWK_TTL", "2592000")
        aws = Aws()
        self.dynamodb = aws.dynamodb_resource
        self.ddbclient = aws.dynamodb

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(JwkStorage, cls).__new__(cls)
        return cls.instance


class Jwk:
    def __init__(self, jwk_storage: JwkStorage, **kwargs):
        init_logger("Jwk")
        self._storage: JwkStorage = jwk_storage
        self.record = JwkRecord(**kwargs)

    def to_json(self):
        return self.record._to_jwk().export_public()

    @staticmethod
    def new(jwk_storage: JwkStorage):
        kid = str(uuid.uuid4())
        aws = Aws()
        kms_client = aws.kms
        kms_key_id = os.getenv("KMS_KEY_ID")
        kms_response = kms_client.get_public_key(KeyId=kms_key_id)
        public_key_bytes = kms_response["PublicKey"]
        public_key_pem = base64.b64encode(
            load_der_public_key(public_key_bytes).public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.PKCS1,
            )
        )
        return Jwk(
            jwk_storage,
            kid=kid,
            public_key_pem=public_key_pem,
            kms_key_id=kms_key_id,
        )

    def __log(self):
        return logging.getLogger("LTIPlatform")

    def load(self, kid: str):
        try:
            response = self._storage.ddbclient.get_item(
                TableName=self._storage.TABLE_NAME,
                Key={"PK": {"S": f"JWK#{kid}"}},
            )
            if "Item" in response:
                deserializer = TypeDeserializer()
                r = deserializer.deserialize({"M": response["Item"]})
                self.record = JwkRecord(**r)

            else:
                self.__log().warning(f"No JWK record found for JWK#{id}.")

            return self
        except botocore.exceptions.ClientError as error:
            msg = f"Error retrieving jwk for JWK#{self.id()}. {json.dumps(error)}"
            self.__log().error(msg)
            raise Exception(msg)

    @staticmethod
    def all(jwk_storage: JwkStorage):

        try:
            dynamodb = jwk_storage.dynamodb
            table = dynamodb.Table(jwk_storage.TABLE_NAME)
            response = table.scan(
                FilterExpression=Attr("PK").begins_with("JWK#"),
                ConsistentRead=True,
            )
            if "Items" in response and len(response["Items"]) > 0:
                keys = []
                now = int(datetime.now().timestamp()) + int(864000)
                for item in response["Items"]:
                    record = JwkRecord(**item)._to_jwk().export_public(as_dict=True)
                    ttl = item["ttl"]
                    record["ttl"] = int(ttl)
                    keys.append(record)
                if len(keys) <= 1 and len([k for k in keys if now - k["ttl"] < 864000]) > 0:
                    Jwk.new(jwk_storage).save()
                    return Jwk.all(jwk_storage)
                else:
                    return {"keys": keys}

            else:
                logging.warning("No JWK records found. Creating and saving new jwk")
                Jwk.new(jwk_storage).save()
                return Jwk.all(jwk_storage)

        except botocore.exceptions.ClientError as error:
            msg = f"Error retrieving jwks. {json.dumps(error)}"
            logging.error(msg)
            raise Exception(msg)

    def save(self):
        self.record.PK = f"JWK#{self.record.kid}"
        self.record.ttl = int(datetime.now().timestamp()) + int(
            self._storage.TTL
        )  # this will auto expire the state in DDB

        try:
            serializer = TypeSerializer()
            item = serializer.serialize(self.record.dict())["M"]
            self.__log().debug(f"Saving: {item}")
            self._storage.ddbclient.put_item(TableName=self._storage.TABLE_NAME, Item=item)
        except botocore.exceptions.ClientError as error:
            msg = f"Error persisting JWK for {self.record.PK}. {error}"
            self.__log().error(msg)
            raise Exception(msg)
        return self
