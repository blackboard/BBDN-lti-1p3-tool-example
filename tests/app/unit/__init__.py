import os

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["TABLE_NAME"] = "test"
os.environ["PARTITION_KEY"] = "PK"
os.environ["STATE_TTL"] = "7200"
os.environ["LTI_TOOLING_API_URL_KEY"] = "/anthology/workshop/lti-tooling/api/url/test"
os.environ["KMS_KEY_ID"] = "test"
os.environ["KMS_SYMMETRIC_KEY_ID"] = "test"
os.environ["LEARN_APPLICATION_KEY_KEY"] = "/FAKE/LEARN_APPLICATION_KEY_KEY"
os.environ["LEARN_APPLICATION_SECRET_KEY"] = "/FAKE/LEARN_APPLICATION_SECRET_KEY"
