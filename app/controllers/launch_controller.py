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
    # Validate the request as per IMS standards: state and id_token
    # ref: https://www.imsglobal.org/spec/security/v1p0/#step-3-authentication-response
    # ref: https://www.imsglobal.org/spec/security/v1p0/#authentication-response-validation
    request_cookie_state = request.cookies.get("state")
    request_post_state = request.values.get("state")
    id_token = request.values.get("id_token")

    if not request_cookie_state:
        abort(400, "InvalidParameterException - Missing state cookie")
    if not request_post_state:
        abort(400, "InvalidParameterException - Missing state")
    if not id_token:
        abort(400, "InvalidParameterException - Missing id_token")

    if request_cookie_state != request_post_state:
        abort(409, "InvalidParameterException - State Mismatch")

    try:
        # Unpack the id_token (JWT) into an object, without validating
        jwt_request = LTIJwtPayload(id_token)
        # Load the config for this deployment using some of the properties of the id_token
        platform = LTIPlatform(LTIPlatformStorage()).load(jwt_request.aud, jwt_request.iss, jwt_request.deployment_id)

        # Will raise exceptions internally if the JWT doesn't validate
        try:
            jwt_request.verify(platform)
        except Exception as e:
            abort(401, e)

        # Load the user's State record
        state: LTIState = LTIState(LTIStateStorage()).load(request_cookie_state)
        # Validate the state and nonce
        if not state.validate(jwt_request.nonce):
            abort(409, "InvalidParameterException - Unable to verify State")

        # Add the id_token (JWT) to the user's State record
        state.record.id_token = id_token

        # Load the global config for this Tool
        lti_tool = LTITool(LTIToolStorage())
        # Request an access token for use for LTI 1.3 based Tool Originating Messages
        lti_token = TokenClient().request_bearer_token(
            platform=platform, grantType=GrantType.CLIENT_CREDENTIALS, tool=lti_tool
        )

        # Add the access token to the user's State record (convenience method to encryption)
        state.record.set_platform_lti_token(lti_token)
        # Save the user's State record
        state.save()

        # Blackboard Three-Legged OAuth (3LO) for Learn REST API
        if jwt_request.platform_product_code == "BlackboardLearn":
            ##################
            # Learn REST access token for accessing the Learn REST API: Authorization Code grant
            # https://docs.blackboard.com/rest-apis/learn/getting-started/3lo
            # https://developer.blackboard.com/portal/displayApi/
            # https://www.oauth.com/oauth2-servers/access-tokens/authorization-code-request/
            ##################
            params = {
                "redirect_uri": lti_tool.config.auth_code_url(),
                "response_type": "code",
                "client_id": lti_tool.config.learn_app_key,  # despite the naming this is the Learn Application Key
                "scope": "*",
                "state": request_post_state,
            }
            encoded_params = urlencode(params)

            learn_url = jwt_request.platform_url.rstrip("/")
            one_time_session_token = jwt_request.one_time_session_token
            auth_code_url = f"{learn_url}/learn/api/public/v1/oauth2/authorizationcode?{encoded_params}&one_time_session_token={one_time_session_token}"
            return redirect(auth_code_url)
        else:
            return render_ui(jwt_request, request_post_state, id_token)
    except Exception as e:
        abort(500, e)


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
    if jwt_request.platform_product_code == "BlackboardLearn":
        course_info = LearnClient().get_course_info(jwt_request, state)
        course_date = course_info["modified"] if "modified" in course_info else ""

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
