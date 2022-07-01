import os

import boto3

cfn_client = boto3.client("cloudformation")

os.environ["AWS_REGION"] = "us-east-1"
os.environ["TABLE_NAME"] = "test"
os.environ["PARTITION_KEY"] = "PK"
os.environ["STATE_TTL"] = "7200"
os.environ["LTI_TOOLING_API_URL_KEY"] = "/anthology/workshop/lti-tooling/api/url/test"
os.environ["KMS_KEY_ID"] = "test"
