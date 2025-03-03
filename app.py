#!/usr/bin/env python3
import os

import aws_cdk as cdk

from elbtest.elbtest_stack import ElbtestStack


app = cdk.App()
ElbtestStack(
    app,
    "LBtestStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
)

app.synth()
