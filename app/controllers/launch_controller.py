import json
import logging
from urllib.parse import urlencode

import requests
from flask import abort
from flask import redirect
from flask import render_template

from app.controllers import rest_auth_controller
from app.models.jwt import LTIJwtPayload
from app.models.platform_config import LTIPlatform
from app.models.platform_config import LTIPlatformStorage
from app.models.state import LTIState
from app.models.state import LTIStateStorage
from app.models.tool_config import LTITool
from app.models.tool_config import LTIToolStorage
from app.utility import init_logger
from app.utility.learn_client import LearnClient
from app.utility.token_client import GrantType
from app.utility.token_client import TokenClient


def launch(request):
    pass


def render_ui(jwt_request: LTIJwtPayload, state, id_token):
    pretty_body = json.dumps(jwt_request.payload, sort_keys=True, indent=2, separators=(",", ": "))

    # Get the user's name; they might not have a "full name"
    if "name" in jwt_request.payload:
        name = jwt_request.payload["name"]
    elif "given_name" in jwt_request.payload:
        name = jwt_request.payload["given_name"]
    else:
        name = "Anonymous"

    tool = LTITool(LTIToolStorage())

    course_date = ""

    if jwt_request.message_type == "LtiResourceLinkRequest":
        action_url = f"{tool.config.base_url()}/submit_assignment"
        return render_template(
            "knowledge_check.html",
            name=name,
            pretty_body=pretty_body,
            id_token=id_token,
            state=state,
            action_url=action_url,
            course_name=jwt_request.context_title,
            course_modified=course_date,
        )
    elif jwt_request.message_type == "LtiDeepLinkingRequest":
        action_url = f"{tool.config.base_url()}/create_assignment"
        return render_template(
            "create_assignment.html",
            name=name,
            pretty_body=pretty_body,
            id_token=id_token,
            action_url=action_url,
        )
    else:
        abort(409, "InvalidParameterException - Unknown message type")

