from aws_cdk import CfnOutput
from aws_cdk import Environment
from aws_cdk import NestedStack
from aws_cdk import Stack
from aws_cdk import Stage
from constructs import Construct

import infrastructure.constructs.tables as tables_
from infrastructure import clean_name
from infrastructure.constructs.application import Application
from infrastructure.constructs.keys import Keys
from infrastructure.constructs.pipeline import Pipeline


class StatefulStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        branch: str,
    ) -> None:
        super().__init__(scope, construct_id)
        self.keys = Keys(self, "keys")
        self.tables = tables_.Tables(self, "tables")


class StatelessStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stateful_stack: StatefulStack,
        branch: str,
    ) -> None:
        super().__init__(scope, construct_id)
        self.application = Application(self, "app", stateful_stack.tables, branch, stateful_stack.keys)


class ApplicationStage(Stage):
    def __init__(
        self,
        scope: Construct,
        id: str,
        env: Environment,
        branch: str,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)
        ApplicationStack(self, f"application-stack-{clean_name(branch)}", env, branch)


class ApplicationStack(Stack):
    def __init__(self, scope: Construct, id: str, env: Environment, branch: str) -> None:
        super().__init__(scope, id, env=env)
        stateful_stack = StatefulStack(self, "stateful-stack", branch)
        CfnOutput(
            self,
            "asymmetric-key-id-output",
            value=stateful_stack.keys.asymmetric_key.key_id,
            export_name="asymmetric-key-id",
        )
        CfnOutput(
            self,
            "symmetric-key-id-output",
            value=stateful_stack.keys.symmetric_key.key_id,
            export_name="symmetric-key-id",
        )
        CfnOutput(
            self,
            "table-name-output",
            value=stateful_stack.tables.lti_table.table_name,
            export_name="table-name",
        )
        stateless_stack = StatelessStack(self, "stateless-stack", stateful_stack, branch)
        CfnOutput(
            self,
            "tool-url-output",
            value=stateless_stack.application.api_url,
            export_name="tool-url",
        )



class PipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        env: Environment,
        codestar_connection_arn: str,
        repo: str,
        branch: str,
    ) -> None:
        super().__init__(scope, id, env=env)
        Pipeline(
            self,
            "pipeline",
            ApplicationStage(self, f"stage-{clean_name(branch)}", env, branch),
            codestar_connection_arn,
            repo,
            branch,
        )
