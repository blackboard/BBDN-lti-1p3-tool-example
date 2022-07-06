import datetime
import json
import logging
import secrets
from calendar import timegm
from enum import Enum
from enum import auto

import requests

from app.models.jwt import LTIJwtPayload
from app.models.platform_config import LTIPlatform
from app.models.state import LTIStateStorage, LTIState
from app.models.tool_config import LTITool
from app.models.tool_config import LTIToolStorage
from app.utility import init_logger


class LearnClient:
    def __init__(self, **kwargs):
        init_logger("LearnClient")

    def __log(self):
        return logging.getLogger("LearnClient")

    def get_course_info(self, jwt_request: LTIJwtPayload, request_cookie_state):
        state: LTIState = LTIState(LTIStateStorage()).load(request_cookie_state)
        learn_access_token = state.record.get_platform_learn_rest_token()
        learn_url = jwt_request.platform_url.rstrip("/")
        course_uuid = jwt_request.context_id
        headers = {"Authorization": f"Bearer {learn_access_token}"}
        course_info_url = f"{learn_url}/learn/api/public/v2/courses/uuid:{course_uuid}"
        response = requests.get(course_info_url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            self.__log().error(
                f"Error getting course info via Learn public API, status: {response.status_code}"
            )
            return {}
