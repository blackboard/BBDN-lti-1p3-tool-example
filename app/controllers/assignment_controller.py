import datetime
import json
import time
import uuid

import requests
from flask import abort
from flask import render_template

from app.models.jwt import LTIJwtPayload
from app.models.state import LTIState
from app.models.state import LTIStateStorage
from app.models.tool_config import LTITool
from app.models.tool_config import LTIToolStorage


def submit_assignment(request):

    question1 = request.form.get("ackOauth", "off")
    question2 = request.form.get("ackGradeReturn", "off")
    question3 = request.form.get("ackREST", "off")
    comment = request.form.get("comment", "")
    request_cookie_state = request.form.get("state")

    if not question1 or not question2 or not question3:
        abort(400, "InvalidParameterException - Missing required parameter")
    if not request_cookie_state:
        abort(400, "InvalidParameterException - Missing state")

    state: LTIState = LTIState(LTIStateStorage()).load(request_cookie_state)
    if not state:
        abort(409, "InvalidParameterException - State not found")

    try:
        id_token = state.record.id_token
        jwt_request = LTIJwtPayload(id_token)

        lti_token = state.record.get_platform_lti_token()
        # Get Learn URL from the JWT
        line_item_url = jwt_request.endpoint_lineitem.rstrip("/")
        name = jwt_request.payload["name"]
        # Calculate score
        score = 0
        if question1 == "on":
            score += 30
        if question2 == "on":
            score += 30
        if question3 == "on":
            score += 30

        # Construct payload for Learning Tools Interoperability (LTI) Assignment and Grade Services (AGS) call
        score_json = {
            "userId": jwt_request.sub,
            "scoreGiven": score,
            "scoreMaximum": 100,
            "comment": comment,
            "timestamp": datetime.datetime.utcnow()
            .replace(tzinfo=datetime.timezone.utc)
            .isoformat(),
            "activityProgress": "Completed",
            "gradingProgress": "FullyGraded",
        }

        headers = {
            "content-type": "application/vnd.ims.lis.v1.score+json",
            "Authorization": f"Bearer {lti_token}",
        }

        # Make AGS call to update grade
        response = requests.post(
            f"{line_item_url}/scores", json=score_json, headers=headers
        )
        pretty_body = json.dumps(
            score_json, sort_keys=True, indent=2, separators=(",", ": ")
        )
        return render_template(
            "submission_success.html",
            status=response.status_code,
            response=response.text,
            pretty_body=pretty_body,
            name=name,
        )
    except Exception as e:
        abort(500, e)


def create_assignment(request):

    name = request.form.get("name")
    points = request.form.get("points")
    id_token = request.form.get("id_token")
    request_cookie_state = request.form.get("state")

    if not name or not points or not id_token:
        abort(400, "InvalidParameterException - Missing required parameter")

    state: LTIState = LTIState(LTIStateStorage()).load(request_cookie_state)
    if not state:
        abort(409, "InvalidParameterException - State not found")

    try:
        jwt_request = LTIJwtPayload(id_token)
        lti_tool = LTITool(LTIToolStorage())

        content = get_assignment_content(name, points)

        return_url = jwt_request.deep_linking_settings_return_url
        deep_link_claims = get_message_claims(jwt_request, content)

        jwt = LTIJwtPayload()
        jwtstring = jwt.encode(payload=deep_link_claims, tool=lti_tool)

        pretty_body = json.dumps(
            deep_link_claims, sort_keys=True, indent=2, separators=(",", ": ")
        )

        return render_template(
            "confirm_assignment.html",
            pretty_body=pretty_body,
            jwt=jwtstring,
            return_url=return_url,
        )
    except Exception as e:
        abort(500, e)

def get_assignment_content(name, points):
    # Mock return value to simulate a assignment content item
    # Ideally we'd create an assignment in our database and create a content item with that unique identifier
    assignment_id = uuid.uuid4().hex

    tool = LTITool(LTIToolStorage())
    lti_launch_url = f"{tool.config.base_url()}/launch"

    content_item = dict(
        type="ltiResourceLink",
        title=name,
        text="Do this assignment",
        url=lti_launch_url,
        lineItem=dict(
            scoreMaximum=points, label=name, resourceId=assignment_id, tag="originality"
        ),
        custom=dict(
            assignment_id=assignment_id,
            userNameLTI="$User.username",
            userIdLTI="$User.id",
            contextHistory="$Context.id.history",
            resourceHistory="$ResourceLink.id.history",
        ),
    )

    return [content_item]


def get_message_claims(jwt_request: LTIJwtPayload, content_items) -> dict:
    claims = {
        "iss": jwt_request.aud,
        "aud": [jwt_request.iss],
        "exp": int(time.time()) + 600,
        "iat": int(time.time()),
        "nonce": "nonce-" + uuid.uuid4().hex,
        "https://purl.imsglobal.org/spec/lti/claim/deployment_id": jwt_request.deployment_id,
        "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiDeepLinkingResponse",
        "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
        "https://purl.imsglobal.org/spec/lti-dl/claim/content_items": content_items,
        "https://purl.imsglobal.org/spec/lti-dl/claim/data": jwt_request.deep_linking_settings_data,
    }
    return claims
