import aws_cdk
from aws_cdk import aws_dynamodb as dynamo_
from constructs import Construct


class Tables(Construct):
    """ """

    def __init__(self, scope: Construct, id: str):
        """

        :param stack:
        :param kwargs:
        """
        super().__init__(scope, id)
        self.partition_key_name = "PK"
        self.lti_table = dynamo_.Table(
            self,
            "lti-table",
            partition_key=dynamo_.Attribute(name=self.partition_key_name, type=dynamo_.AttributeType.STRING),
            time_to_live_attribute="ttl",
            billing_mode=dynamo_.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=aws_cdk.RemovalPolicy.DESTROY,
        )
