import logging

import aws_lambda_wsgi

from app import create_app
from app.utility import init_logger
from flask import render_template
import werkzeug

application = create_app()


@application.errorhandler(werkzeug.exceptions.HTTPException)
def application_error_handler(e):
    __log().error(e)
    response = application.make_response(render_template("error.html", error=e))
    return response


def lambda_handler(event, context):
    __log().debug(f"Event: {event}")
    return aws_lambda_wsgi.response(application, event, context)


def __log():
    return logging.getLogger("app.endpoint")


init_logger("app.endpoint")
