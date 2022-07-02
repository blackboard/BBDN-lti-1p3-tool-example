import datetime
import json
import time
import uuid

import requests
from flask import render_template

# TODO: encapsulate into a single responsibility area
from app.models.jwt import LTIJwtPayload
from app.models.state import LTIState
from app.models.state import LTIStateStorage
from app.models.tool_config import LTITool
from app.models.tool_config import LTIToolStorage


def get_message_claims(jwt_request: LTIJwtPayload, content_items) -> dict:
    """

    :param payload:
    :param content_items:
    :return:
    """
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


def create_assignment(request):
    """

    :return:
    """

    name = request.form.get("name", "err")
    points = request.form.get("points", "err")
    id_token = request.form.get("id_token", "err")
    jwt_request = LTIJwtPayload(id_token)
    lti_tool = LTITool(LTIToolStorage())

    content = get_assignment_content(name, points)

    return_url = jwt_request.deep_linking_settings_return_url
    deep_link_jwt = get_message_claims(jwt_request, content)

    jwt = LTIJwtPayload()
    jwtstring = jwt.encode(payload=deep_link_jwt, tool=lti_tool)

    pretty_body = json.dumps(deep_link_jwt, sort_keys=True, indent=2, separators=(",", ": "))

    return render_template(
        "confirm_assignment.html",
        pretty_body=pretty_body,
        jwt=jwtstring,
        return_url=return_url,
    )


def get_assignment_content(name, points):
    # Ideally we'd create an assignment in our database and create a content item with that unique identifier
    assignment_id = uuid.uuid4().hex

    tool = LTITool(LTIToolStorage())
    lti_launch_url = f"{tool.config.base_url()}/launch"

    content_item = dict(
        type="ltiResourceLink",
        title=name,
        text="Do this assignment",
        url=lti_launch_url,
        icon=dict(
            url="https://static.thenounproject.com/png/1993078-200.png",
            width=100,
            height=100,
        ),
        lineItem=dict(scoreMaximum=points, label=name, resourceId=assignment_id, tag="originality"),
        custom=dict(
            assignment_id=assignment_id,
            userNameLTI="$User.username",
            userIdLTI="$User.id",
            contextHistory="$Context.id.history",
            resourceHistory="$ResourceLink.id.history",
        ),
    )

    return [content_item]


def submit_assignment(request):
    """

    :return:
    """

    question1 = request.form.get("ackOauth", "off")
    question2 = request.form.get("ackGradeReturn", "off")
    question3 = request.form.get("ackREST", "off")
    comment = request.form.get("comment", "")

    request_cookie_state = request.form.get("state")
    state: LTIState = LTIState(LTIStateStorage()).load(request_cookie_state)
    lti_token = state.record.get_platform_lti_token()
    id_token = state.record.id_token
    jwt_request = LTIJwtPayload(id_token)

    # Calculate score
    score = 0
    if question1 == "on":
        score += 30
    if question2 == "on":
        score += 30
    if question3 == "on":
        score += 30

    # Get Learn URL
    line_item_url = jwt_request.payload["https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"]["lineitem"].rstrip(
        "/"
    )

    # Construct payload for AGS call
    score_json = {
        "userId": jwt_request.sub,
        "scoreGiven": score,
        "scoreMaximum": 100,
        "comment": comment,
        "timestamp": datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat(),
        "activityProgress": "Completed",
        "gradingProgress": "FullyGraded",
    }

    headers = {
        "content-type": "application/vnd.ims.lis.v1.score+json",
        "Authorization": f"Bearer {lti_token}",
    }

    # Make AGS call to update grade
    response = requests.post(f"{line_item_url}/scores", json=score_json, headers=headers)

    return render_template("submission_success.html", status=response.status_code, response=response.text)
