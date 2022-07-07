from urllib.parse import urlencode
from urllib.parse import urljoin

from flask import abort
from flask import redirect

from app.models.platform_config import LTIPlatform
from app.models.platform_config import LTIPlatformStorage
from app.models.state import LTIState
from app.models.state import LTIStateStorage


def login(request):
    client_id = request.values.get("client_id")
    issuer = request.values.get("iss")
    login_hint = request.values.get("login_hint")
    lti_deployment_id = request.values.get("lti_deployment_id")
    lti_message_hint = request.values.get("lti_message_hint")
    target_link_uri = request.values.get("target_link_uri")

    if not client_id:
        abort(400, "InvalidParameterException - Missing client_id")
    if not issuer:
        abort(400, "InvalidParameterException - Missing issuer")
    if not login_hint:
        abort(400, "InvalidParameterException - Missing login_hint")
    if not lti_deployment_id:
        abort(400, "InvalidParameterException - Missing lti_deployment_id")
    if not target_link_uri:
        abort(400, "InvalidParameterException - Missing target_link_url")

    try:
        lti_platform = LTIPlatform(LTIPlatformStorage()).load(client_id, issuer, lti_deployment_id)
        state = LTIState(LTIStateStorage()).save()
        auth_url = lti_platform.config.auth_login_url
        query_params = dict(
            scope="openid",
            response_type="id_token",
            client_id=client_id,
            redirect_uri=target_link_uri,
            state=state.record.id,
            nonce=state.record.nonce,
            login_hint=login_hint,
        )

        if lti_message_hint:
            query_params.update(lti_message_hint=lti_message_hint)

        query = "?" + urlencode(query_params)

        redirect_url = urljoin(auth_url, query)
        resp = redirect(redirect_url)
        resp.set_cookie(
            key="state",
            value=state.record.id,
            samesite="None",
            secure=True,
            httponly=True,
        )

        return resp
    except Exception as e:
        abort(500, e)