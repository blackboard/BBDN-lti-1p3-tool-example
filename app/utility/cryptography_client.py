import base64
import logging
import os

from app.utility import init_logger
from app.utility.aws import Aws


class CryptographyClient:
    def __init__(self, **kwargs):
        init_logger("CryptographyClient")

    @staticmethod
    def encrypt_string(plaintext: str) -> str:
        if plaintext is None and len(plaintext) == 0:
            return ""
        else:
            aws = Aws()
            kmsclient = aws.kms

            try:
                kms_response = kmsclient.encrypt(
                    KeyId=os.getenv("KMS_SYMMETRIC_KEY_ID"),
                    Plaintext=plaintext.encode("utf-8"),
                )
                return base64.encodebytes(kms_response.get("CiphertextBlob", "")).decode("utf-8")
            except Exception as e:
                msg = f"Error encrypting string: {e}"
                logging.error(msg)
                raise Exception(msg)

    @staticmethod
    def decrypt_string(cyphertext: str) -> str:
        if cyphertext is None and len(cyphertext) == 0:
            return ""
        else:
            aws = Aws()

            kmsclient = aws.kms

            try:
                kms_response = kmsclient.decrypt(
                    KeyId=os.getenv("KMS_SYMMETRIC_KEY_ID"),
                    CiphertextBlob=base64.decodebytes(cyphertext.encode("utf-8")),
                )
                return kms_response.get("Plaintext", "").decode("utf-8")
            except Exception as e:
                msg = f"Error decrypting string: {e}"
                logging.error(msg)
                raise Exception(msg)
