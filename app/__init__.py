"""
app.__init__
------------
Application factory
"""

from flask import Flask

from app.controllers.routes import blueprint


def init_app() -> Flask:
    """
    :return:
    """
    application = Flask(__name__)
    application.register_blueprint(blueprint)
    return application


def create_app(config=None):
    """
    :param config:
    :return:
    """
    application = init_app()
    return application
