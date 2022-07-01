#!/usr/bin/env python3

from aws_cdk import App
from aws_cdk import Environment

from infrastructure.stacks import ApplicationStack

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
ApplicationStack(app, "workshop-application-stack", Environment(), "main")
app.synth()
