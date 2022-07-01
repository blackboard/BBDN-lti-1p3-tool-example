import boto3


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Aws(metaclass=Singleton):
    def __init__(self, **kwargs):
        self.ssm = kwargs["ssm"] if "ssm" in kwargs else boto3.client("ssm")
        self.dynamodb = kwargs["dynamodb"] if "dynamodb" in kwargs else boto3.client("dynamodb")
        self.dynamodb_resource = (
            kwargs["dynamodb_resource"] if "dynamodb_resource" in kwargs else boto3.resource("dynamodb")
        )
        self.kms = kwargs["kms"] if "kms" in kwargs else boto3.client("kms")
