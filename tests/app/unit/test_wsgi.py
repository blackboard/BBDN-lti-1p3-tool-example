import json
import os
import time
from datetime import datetime
from unittest.mock import MagicMock
from urllib import parse
import requests
import requests_mock
import boto3
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import rsa
from jwcrypto.jwk import JWK
from jwt import PyJWKClient
from jwt import PyJWT
from moto import mock_dynamodb
from moto import mock_kms
from moto import mock_ssm

from app import wsgi
from app.models.jwks import Jwk
from app.models.jwks import JwkStorage
from app.models.state import LTIState
from app.models.state import LTIStateStorage
from app.models.tool_config import LTITool
from app.models.tool_config import LTIToolStorage
from app.utility.aws import Aws
from tests.app import handle_exception
from tests.app import read_file


@pytest.fixture(scope="function")
def ssm():
    with mock_ssm():
        ssm_client = boto3.client("ssm")
        ssm_client.put_parameter(
            Name=os.getenv("LTI_TOOLING_API_URL_KEY"),
            Value="http://localhost/api",
        )
        ssm_client.put_parameter(
            Name=os.getenv("LEARN_APPLICATION_KEY_KEY"),
            Value="FAKE_LEARN_KEY",
        )
        ssm_client.put_parameter(
            Name=os.getenv("LEARN_APPLICATION_SECRET_KEY"),
            Value="FAKE_LEARN_SECRET",
            Type="SecureString",
        )
        yield ssm_client


@pytest.fixture(scope="function")
def dynamodb():

    with mock_dynamodb():
        dynamodb = boto3.client("dynamodb")
        dynamodb.create_table(
            TableName=os.getenv("TABLE_NAME"),
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
            ],
        )
        dynamodb.Table = MagicMock()
        dynamodb.Table.scan = MagicMock(return_value="Hello")
        yield dynamodb


@pytest.fixture(scope="function")
def kms(public_key_der, rsa_private_key):

    with mock_kms():
        kms = boto3.client("kms")
        kms.get_public_key = MagicMock(return_value={"PublicKey": public_key_der})

        def mock_sign(*args, **kwargs):
            message = kwargs["Message"]
            signature = rsa_private_key.sign(
                message.encode("utf-8"),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return {"Signature": signature}

        kms.sign = MagicMock(side_effect=mock_sign)
        yield kms


@pytest.fixture(scope="function")
def aws(dynamodb, kms, ssm):
    return Aws(dynamodb=dynamodb, kms=kms, ssm=ssm)


@pytest.fixture(scope="function")
def key_pair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.PKCS1
    )
    public_key_der = key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_key, public_key_der, key


@pytest.fixture(scope="function")
def public_key(key_pair):
    return key_pair[1]


@pytest.fixture(scope="function")
def public_key_der(key_pair):
    return key_pair[2]


@pytest.fixture(scope="function")
def private_key(key_pair):
    return key_pair[0]


@pytest.fixture(scope="function")
def rsa_private_key(key_pair) -> rsa.RSAPrivateKey:
    return key_pair[3]


@pytest.fixture(scope="function")
def platform_jwks(public_key) -> dict:
    jwks = JWK()
    jwks.import_from_pem(data=public_key, kid="75363971-2683-4ad9-a31b-93ec41e27772")
    return {"keys": [jwks.export_public(as_dict=True)]}


@pytest.fixture(scope="function")
def lti_tool(aws) -> LTITool:
    return LTITool(LTIToolStorage())


@pytest.fixture(scope="function")
def id_token(private_key, state):
    token_payload = read_file(
        "token_payload.json",
        {
            '"NOW"': str(int(datetime.now().timestamp())),
            '"EXPIRATION"': str(int(datetime.now().timestamp() + 300)),
            "NONCE": str(state.record.nonce),
        },
    )
    pyjwt = PyJWT()
    id_token = pyjwt.encode(
        payload=token_payload,
        key=private_key,
        algorithm="RS256",
        headers={"kid": "75363971-2683-4ad9-a31b-93ec41e27772", "alg": "RS256"},
    )
    return id_token


@pytest.fixture(scope="function")
def state(dynamodb):
    return LTIState(LTIStateStorage()).save()


def test_multiple_jwks(aws, lti_tool, public_key):

    expected_jwks = lti_tool.jwks
    time.sleep(5)
    request_event = read_file("get_tool_jwks.json")
    wsgi.application.register_error_handler(Exception, handle_exception)
    response = wsgi.lambda_handler(request_event, {})
    assert response
    assert response["statusCode"] == 200
    actual_jwks = json.loads(response["body"])
    sorted_kids = lti_tool.tool_kids()
    assert len(sorted_kids) == 2
    assert actual_jwks == expected_jwks


def test_jwks(aws, lti_tool, public_key):

    expected_jwks = lti_tool.jwks
    request_event = read_file("get_tool_jwks.json")
    wsgi.application.register_error_handler(Exception, handle_exception)
    response = wsgi.lambda_handler(request_event, {})
    assert response
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == expected_jwks


def test_launch(aws, id_token, platform_jwks, state):

    register_lti_platforms(aws.dynamodb)
    request_event = read_file(
        "launch.json",
        {"{STATE}": state.record.id, "{ID_TOKEN}": id_token},
    )
    PyJWKClient.fetch_data = MagicMock(return_value=platform_jwks)
    wsgi.application.register_error_handler(Exception, handle_exception)
    with requests_mock.Mocker() as m:
        m.post(
            url="https://developer.blackboard.com/api/v1/gateway/oauth2/jwttoken",
            status_code=200,
            text=json.dumps({"access_token": "fake_token"}),
        )
        response = wsgi.lambda_handler(request_event, {})
        assert response
        assert response["statusCode"] == 302


def test_platform_register(dynamodb):
    request_event = read_file("platform.json")
    wsgi.application.register_error_handler(Exception, handle_exception)
    response = wsgi.lambda_handler(request_event, {})
    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/json; charset=utf-8"
    assert (
        response["body"]
        == '{"PK": "CONFIG#75363971-2683-4ad9-a31b-93ec41e27772#https://blackboard.com#f66151aa-a799-4b22-93ed-81dd16f70a4e", "auth_token_url": "https://developer.blackboard.com/api/v1/gateway/oauth2/jwttoken", "auth_login_url": "https://developer.blackboard.com/api/v1/gateway/oidcauth", "client_id": "75363971-2683-4ad9-a31b-93ec41e27772", "lti_deployment_id": "f66151aa-a799-4b22-93ed-81dd16f70a4e", "iss": "https://blackboard.com", "key_set_url": "https://developer.blackboard.com/api/v1/management/applications/75363971-2683-4ad9-a31b-93ec41e27772/jwks.json", "learn_application_key": null, "learn_application_secret": null}'
    )


def test_login(dynamodb):

    register_lti_platforms(dynamodb)
    request_event = read_file("oidc.json")

    wsgi.application.register_error_handler(Exception, handle_exception)
    response = wsgi.lambda_handler(request_event, {})
    assert response
    assert response["statusCode"] == 302
    assert response["headers"]["Content-Type"] == "text/html; charset=utf-8"
    assert "Location" in response["headers"]
    assert "Set-Cookie" in response["headers"]
    query = dict(parse.parse_qs(parse.urlsplit(response["headers"]["Location"]).query))
    assert query["scope"][0] == "openid"
    assert query["response_type"][0] == "id_token"
    assert query["client_id"][0] == "75363971-2683-4ad9-a31b-93ec41e27772"
    assert (
        query["redirect_uri"][0]
        == "https://ymhk99ns7g.execute-api.us-east-2.amazonaws.com/prod/launch"
    )
    assert (
        query["login_hint"][0]
        == "https%3A%2F%2Flearn25.anthology.workshops.aws.dev%2Fwebapps%2Fblackboard%2Fexecute%2Fblti%2FlaunchPlacement%3Fcmd%3Dauthenticate%26course_id%3D_3_1,10ac1fc7a50c4433ae104c283cc66e47,67934c629a3845f8beb2f71241e3b13f"
    )
    assert (
        query["lti_message_hint"][0]
        == "eyJwbGFjZW1lbnRJZCI6Il85XzEiLCJwb3NpdGlvbiI6LTEsIm9wZW5JbkxpZ2h0Qm94IjpmYWxzZSwiZnJvbVVsdHJhIjpmYWxzZSwiaW5saW5lTW9kZSI6ZmFsc2UsInRhcmdldExpbmtVcmwiOiJodHRwczovL3ltaGs5OW5zN2cuZXhlY3V0ZS1hcGkudXMtZWFzdC0yLmFtYXpvbmF3cy5jb20vcHJvZC9pbXMvbGF1bmNoIiwicmVzb3VyY2VMaW5rSWQiOiJfM18xc2lnbi11cC1saXN0IiwiY291cnNlSWQiOiJfM18xIiwiY29udGVudElkIjpudWxsLCJwYXJlbnRDb250ZW50SWQiOiIiLCJjdXN0b21QYXJhbXMiOnt9LCJ0YXJnZXRPdmVycmlkZSI6bnVsbCwiZnJvbUdyYWRlQ2VudGVyIjpmYWxzZSwib3Blbk5ld1dpbmRvdyI6ZmFsc2UsImRlZXBMaW5rTGF1bmNoIjpmYWxzZX0="
    )


def register_tool_jwks(dynamodb, tool_jwks):
    dynamodb.put_item(
        TableName=os.getenv("TABLE_NAME"),
        Item={
            "PK": {"S": "JWK#db9de74b-4990-4acf-af63-0da8adeb2a49"},
            "kid": {"S": "db9de74b-4990-4acf-af63-0da8adeb2a49"},
            "kms_key_id": {
                "S": "arn:aws:kms:us-east-2:200982613275:key/02f144bb-80c8-42ba-836b-d4248bd876c3"
            },
            "public_key_pem": {
                "S": "LS0tLS1CRUdJTiBSU0EgUFVCTElDIEtFWS0tLS0tCk1JSUJDZ0tDQVFFQXByY1Y0dW0ydFpzUkttV2JUUFpySUp0T3ZicDBWV0lRanBvWnhyZmR1OFI0YWlWWjR0UE0KY04zY2x2ZVl5TEY0VThzSnNjS3ZrT3AwbGJVZ2dtRzRCWlI3NFkveko1NW9IZjZ4NTV1WktIbDZJOGNTZmtGLwpic0pqM2I4R0VPNnU0QjhGVFpsQ3c0dWhJemFXTyt3eEJuRmhzaWx0WFpBa3JvcXNPa1Q2dDlvU2FJRXVya3pECm43L2g3K0NxTklKWXlEOTNFZytGKzhaTUpjVjRITThMVTlKRWUxWW10eDFndk02OXNsNHByRndoM2JJN2FvV00KSG9GYlVKT2czUFlIQ0UxRml4MlZ0b0t6K3ptL0FETnRqeVhMSU1OMWR4MGkwSThTcWVmR2x2QVdyWXBlVjhqbwpuNDM0dm9Cbm4xcHdKelJyNklvbi9Ba25VRXBlVG94YTN3SURBUUFCCi0tLS0tRU5EIFJTQSBQVUJMSUMgS0VZLS0tLS0K"
            },
            "ttl": {"N": "1658684348"},
        },
    )


def register_lti_platforms(dynamodb):
    dynamodb.put_item(
        TableName=os.getenv("TABLE_NAME"),
        Item={
            "PK": {
                "S": "CONFIG#75363971-2683-4ad9-a31b-93ec41e27772#https://blackboard.com#f66151aa-a799-4b22-93ed-81dd16f70a4e"
            },
            "auth_login_url": {
                "S": "https://developer.blackboard.com/api/v1/gateway/oidcauth"
            },
            "auth_token_url": {
                "S": "https://developer.blackboard.com/api/v1/gateway/oauth2/jwttoken"
            },
            "client_id": {"S": "75363971-2683-4ad9-a31b-93ec41e27772"},
            "iss": {"S": "https://blackboard.com"},
            "key_set_url": {
                "S": "https://developer.blackboard.com/api/v1/management/applications/75363971-2683-4ad9-a31b-93ec41e27772/jwks.json"
            },
            "lti_deployment_id": {"S": "f66151aa-a799-4b22-93ed-81dd16f70a4e"},
        },
    )
    dynamodb.put_item(
        TableName=os.getenv("TABLE_NAME"),
        Item={
            "PK": {"S": "CONFIG#1234#https://blackboard.com#4567"},
            "auth_login_url": {"S": "www.example.org/login"},
            "auth_token_url": {"S": "www.example.org/token"},
            "client_id": {"S": "1234"},
            "iss": {"S": "https://blackboard.com"},
            "key_set_url": {"S": "www.example.org/key/jwks.json"},
            "lti_deployment_id": {"S": "4567"},
        },
    )


def test_new_jwks(kms):
    item = {
        "public_key_pem": "LS0tLS1CRUdJTiBSU0EgUFVCTElDIEtFWS0tLS0tCk1JSUJDZ0tDQVFFQXByY1Y0dW0ydFpzUkttV2JUUFpySUp0T3ZicDBWV0lRanBvWnhyZmR1OFI0YWlWWjR0UE0KY04zY2x2ZVl5TEY0VThzSnNjS3ZrT3AwbGJVZ2dtRzRCWlI3NFkveko1NW9IZjZ4NTV1WktIbDZJOGNTZmtGLwpic0pqM2I4R0VPNnU0QjhGVFpsQ3c0dWhJemFXTyt3eEJuRmhzaWx0WFpBa3JvcXNPa1Q2dDlvU2FJRXVya3pECm43L2g3K0NxTklKWXlEOTNFZytGKzhaTUpjVjRITThMVTlKRWUxWW10eDFndk02OXNsNHByRndoM2JJN2FvV00KSG9GYlVKT2czUFlIQ0UxRml4MlZ0b0t6K3ptL0FETnRqeVhMSU1OMWR4MGkwSThTcWVmR2x2QVdyWXBlVjhqbwpuNDM0dm9Cbm4xcHdKelJyNklvbi9Ba25VRXBlVG94YTN3SURBUUFCCi0tLS0tRU5EIFJTQSBQVUJMSUMgS0VZLS0tLS0K",
        "ttl": "1658684348",
        "PK": "JWK#db9de74b-4990-4acf-af63-0da8adeb2a49",
        "kms_key_id": "arn:aws:kms:us-east-2:200982613275:key/02f144bb-80c8-42ba-836b-d4248bd876c3",
        "kid": "db9de74b-4990-4acf-af63-0da8adeb2a49",
    }
    r = Jwk(JwkStorage(), **item).to_json()
