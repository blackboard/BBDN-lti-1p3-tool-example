import logging

import aws_lambda_wsgi

from app import create_app
from app.utility import init_logger

# Need to use pipelines to get the right crypto libs
# application = create_app()
application = create_app()


def lambda_handler(event, context):
    __log().debug(f"Event: {event}")
    return aws_lambda_wsgi.response(application, event, context)


def __log():
    return logging.getLogger("app.endpoint")


init_logger("app.endpoint")
