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
    pass


def create_assignment(request):
    pass

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
