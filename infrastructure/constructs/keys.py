import aws_cdk
from aws_cdk import Aws
from aws_cdk import aws_iam
from aws_cdk import aws_kms
from constructs import Construct


class Keys(Construct):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)
        self.asymmetric_key = aws_kms.Key(
            self,
            "lti-asymmetric-key",
            key_spec=aws_kms.KeySpec.RSA_2048,
            key_usage=aws_kms.KeyUsage.SIGN_VERIFY,
            removal_policy=aws_cdk.RemovalPolicy.DESTROY,
            pending_window=aws_cdk.Duration.days(7),
            description="KMS key for signing and verification of JSON Web Tokens (JWT)",
            enable_key_rotation=False,
        )
        self.symmetric_key = aws_kms.Key(
            self,
            "lti-symmetric-key",
            key_spec=aws_kms.KeySpec.SYMMETRIC_DEFAULT,
            key_usage=aws_kms.KeyUsage.ENCRYPT_DECRYPT,
            removal_policy=aws_cdk.RemovalPolicy.DESTROY,
            description="KMS key for encrypting and decrypting of values that are persisted",
            pending_window=aws_cdk.Duration.days(7),
            enable_key_rotation=False,
        )

    def grant_read(self, grantee: aws_iam.IGrantable):

        grantee.grant_principal.add_to_principal_policy(
            aws_iam.PolicyStatement(
                actions=["kms:Verify", "kms:GetPublicKey", "kms:Sign"],
                effect=aws_iam.Effect.ALLOW,
                resources=[
                    f"arn:{Aws.PARTITION}:kms:{Aws.REGION}:{Aws.ACCOUNT_ID}:key/{self.asymmetric_key.key_id}",
                ],
            )
        )
        grantee.grant_principal.add_to_principal_policy(
            aws_iam.PolicyStatement(
                actions=["kms:Encrypt", "kms:Decrypt"],
                effect=aws_iam.Effect.ALLOW,
                resources=[
                    f"arn:{Aws.PARTITION}:kms:{Aws.REGION}:{Aws.ACCOUNT_ID}:key/{self.symmetric_key.key_id}",
                ],
            )
        )
