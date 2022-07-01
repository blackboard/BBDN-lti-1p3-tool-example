import aws_cdk
from aws_cdk import aws_apigateway
from aws_cdk import aws_iam
from aws_cdk import aws_ssm
from constructs import Construct

import infrastructure.constructs.lambdas as lambdas
import infrastructure.constructs.tables as tables_
from infrastructure import clean_name
from infrastructure.constructs.keys import Keys


class Application(Construct):
    def __init__(self, scope: Construct, id: str, tables: tables_.Tables, branch: str, keys: Keys):
        super().__init__(scope, id)
        deps_layer = lambdas.deps_layer(self, branch)
        environment = {
            "TABLE_NAME": tables.lti_table.table_name,
            "KMS_KEY_ID": keys.asymmetric_key.key_arn,
            "KMS_SYMMETRIC_KEY_ID": keys.symmetric_key.key_arn,
            "STATE_TTL": "7200",
            "LTI_TOOLING_API_URL_KEY": f"/anthology/workshop/lti-tooling/api/url/{self.node.path}",
            "LEARN_APPLICATION_KEY_KEY": f"/anthology/workshop/learn/application/key/{self.node.path}",
            "LEARN_APPLICATION_SECRET_KEY": f"/anthology/workshop/learn/application/secret/{self.node.path}",
        }
        flask_endpoint_function, flask_endpoint_alias = lambdas.flask_endpoint_lambda(
            self, environment=environment, branch=branch
        )
        keys.grant_read(flask_endpoint_function)
        flask_endpoint_function.add_layers(deps_layer)
        tables.lti_table.grant_read_write_data(flask_endpoint_function)
        api = aws_apigateway.LambdaRestApi(
            self,
            f"api-{clean_name(branch)}",
            handler=flask_endpoint_function,
            proxy=False,
        )

        api.root.add_method("GET")
        proxy = api.root.add_resource("{proxy+}")
        proxy.add_method("GET")
        proxy.add_method("POST")
        param_api_url = aws_ssm.StringParameter(
            self,
            "lti_tooling_api_url",
            type=aws_ssm.ParameterType.STRING,
            parameter_name=environment["LTI_TOOLING_API_URL_KEY"],
            string_value=api.deployment_stage.url_for_path("/"),
        )
        param_api_url.apply_removal_policy(aws_cdk.RemovalPolicy.DESTROY)
        # Causes circular dependency, manually construct an inline policy and attach it to the execution role.
        # param_api_url.grant_read(lambdaOIDC);
        policy = aws_iam.Policy(
            self,
            "lti-tooling-lambda-read-ssm",
            policy_name="lti_tooling_lambda_read_ssm",
            statements=[
                aws_iam.PolicyStatement(
                    actions=["ssm:GetParameter", "ssm:PutParameter"],
                    resources=[
                        param_api_url.parameter_arn,
                        f"arn:{aws_cdk.Aws.PARTITION}:ssm:{aws_cdk.Aws.REGION}:{aws_cdk.Aws.ACCOUNT_ID}:parameter{environment['LEARN_APPLICATION_KEY_KEY']}",
                        f"arn:{aws_cdk.Aws.PARTITION}:ssm:{aws_cdk.Aws.REGION}:{aws_cdk.Aws.ACCOUNT_ID}:parameter{environment['LEARN_APPLICATION_SECRET_KEY']}",
                    ],
                )
            ],
        )

        policy.attach_to_role(flask_endpoint_function.role)
        self.api_url = api.url
