#!/usr/bin/env python3
import os

from aws_cdk import App
from aws_cdk import Environment

from infrastructure import clean_name
from infrastructure.stacks import PipelineStack

# For consistency with TypeScript code, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
# import pydevd_pycharm
#
# pydevd_pycharm.settrace(
#     "localhost", port=4343, stdoutToServer=True, stderrToServer=True
# )

app = App()
account = app.node.try_get_context("account")
if account is None:
    account = os.environ.get("AWS_DEFAULT_ACCOUNT", os.environ.get("CDK_DEFAULT_ACCOUNT"))
region = app.node.try_get_context("region")
if region is None:
    region = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("CDK_DEFAULT_REGION"))
repo = app.node.try_get_context("repo")
if repo is None:
    repo = os.environ.get("REPO", "blackboard/BBDN-Sign-Up-List-Tool")
branch = app.node.try_get_context("branch")
if branch is None:
    branch = os.environ.get("BRANCH", os.environ.get("USER"))
codestar_connection_arn = app.node.try_get_context("codestar_connection_arn")
if codestar_connection_arn is None:
    codestar_connection_arn = os.environ.get("CODESTAR_CONNECTION_ARN")

if (
    region is not None
    and account is not None  # noqa
    and repo is not None  # noqa
    and branch is not None  # noqa
    and codestar_connection_arn is not None  # noqa
):
    env = Environment(account=account, region=region)
else:
    raise RuntimeError("You must specify account, region, repo, branch, and codestar_connection_arn via context")

print(
    f"Account #: {env.account}, Region: {env.region}, Repo: {repo}, Branch: {branch}, Clean Branch: {clean_name(branch)}, Codestar Connection Arn: {codestar_connection_arn}"
)

PipelineStack(
    app,
    f"pipeline-stack-{clean_name(branch)}",
    env,
    codestar_connection_arn,
    repo,
    branch,
)

app.synth()
