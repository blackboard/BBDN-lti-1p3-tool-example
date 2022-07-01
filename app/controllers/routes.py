import json
import logging

from flask import Blueprint
from flask import current_app
from flask import request

from app.controllers import assignment_controller
from app.controllers import config_controller
from app.controllers import launch_controller
from app.controllers import oidc_controller
from app.controllers import platform_controller
from app.utility import init_logger

blueprint = Blueprint("", __name__, template_folder="templates")


@blueprint.route("/")
def home():
    rules = []
    for rule in current_app.url_map.iter_rules():
        methods = ",".join(sorted(rule.methods))
        rules.append({"path": str(rule), "endpoint": rule.endpoint, "methods": methods})
    return (
        json.dumps(rules),
        200,
        {"Content-Type": "application/json; charset=utf-8"},
    )


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    return oidc_controller.login(request)


@blueprint.route("/launch", methods=["GET", "POST"])
def launch():
    return launch_controller.launch(request)


@blueprint.route("/authcode")
def authcode():
    return launch_controller.authcode(request)


@blueprint.route("/create_assignment", methods=["POST"])
def create_assignment():
    return assignment_controller.create_assignment(request)


@blueprint.route("/submit_assignment", methods=["POST"])
def submit_assignment():
    return assignment_controller.submit_assignment(request)


@blueprint.route("/jwks.json")
def jwks_json():
    return config_controller.jwks()


@blueprint.route("/config")
def config():
    return platform_controller.config()


@blueprint.route("/platform", methods=["POST"])
def register():
    return platform_controller.register(request)


def __log():
    return logging.getLogger("routes")


init_logger("routes")
