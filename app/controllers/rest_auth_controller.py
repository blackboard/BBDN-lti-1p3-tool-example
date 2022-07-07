from flask import abort

from app.controllers import launch_controller
from app.models.jwt import LTIJwtPayload
from app.models.state import LTIStateStorage, LTIState
from app.models.tool_config import LTITool
from app.models.tool_config import LTIToolStorage
from app.utility.token_client import TokenClient


def authcode(request):
    auth_code = request.args.get("code", "")
    request_cookie_state = request.cookies.get("state")

    if not auth_code:
        abort(400, "InvalidParameterException - Missing auth code")
    if not request_cookie_state:
        abort(400, "InvalidParameterException - Missing state")

    state: LTIState = LTIState(LTIStateStorage()).load(request_cookie_state)
    if not state:
        abort(409, "InvalidParameterException - State not found")

    try:
        id_token = state.record.id_token
        jwt_request = LTIJwtPayload(id_token)

        lti_tool = LTITool(LTIToolStorage())
        auth_code_url = lti_tool.config.auth_code_url()

        # Get the Learn access token
        if jwt_request.platform_product_code == "BlackboardLearn":
            learn_url = jwt_request.platform_url.rstrip("/")
            learn_access_token = TokenClient().get_learn_access_token(learn_url, auth_code_url, auth_code)
            # Cache the REST access token
            state.record.set_platform_learn_rest_token(learn_access_token)
            state.save()

        return launch_controller.render_ui(jwt_request, request_cookie_state, id_token)
    except Exception as e:
        abort(500, e)