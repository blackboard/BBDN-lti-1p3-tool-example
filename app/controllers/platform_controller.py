import json

from flask import abort
from flask import render_template

from app.models.platform_config import LTIPlatform
from app.models.platform_config import LTIPlatformConfig
from app.models.platform_config import LTIPlatformStorage
from app.models.tool_config import LTITool
from app.models.tool_config import LTIToolStorage


def config():
    tool = LTITool(LTIToolStorage())
    action_url = f"{tool.config.base_url()}/platform"
    return render_template("config.html", action_url=action_url, base_url=tool.config.base_url())


def register(request):
    if request.data:
        data = json.loads(request.data)
    elif request.form.get("config"):
        data = json.loads(request.form.get("config"))
    elif request.form.get("auth_token_url"):
        # The user entered individual fields
        data = dict(
            auth_token_url=request.form.get("auth_token_url"),
            auth_login_url=request.form.get("auth_login_url"),
            client_id=request.form.get("client_id"),
            lti_deployment_id=request.form.get("lti_deployment_id"),
            iss=request.form.get("iss"),
            key_set_url=request.form.get("key_set_url"),
        )
    else:
        abort(400, "InvalidParameterException - missing config data")

    data["PK"] = ""
    config = LTIPlatformConfig(
        **data,
    )

    if not config.client_id:
        abort(400, "InvalidParameterException - Missing lti_deployment_id")
    if not config.lti_deployment_id:
        abort(400, "InvalidParameterException - Missing lti_deployment_id")
    if not config.auth_token_url:
        abort(400, "InvalidParameterException - Missing auth_token_url")
    if not config.auth_login_url:
        abort(400, "InvalidParameterException - Missing auth_login_url")
    if not config.iss:
        abort(400, "InvalidParameterException - Missing iss")
    if not config.key_set_url:
        abort(400, "InvalidParameterException - Missing key_set_url")

    # Get the Learn application key and secret and save them
    learn_app_key = request.form.get("learn_app_key")
    learn_app_secret = request.form.get("learn_app_secret")

    tool = LTITool(LTIToolStorage())
    if learn_app_secret and learn_app_key:
        tool.set_learn_app_key_and_secret(learn_app_key, learn_app_secret)

    try:
        platform = LTIPlatform(LTIPlatformStorage(), config=config).save()

        return (
            platform.config.json(),
            200,
            {"Content-Type": "application/json; charset=utf-8"},
        )
    except Exception as e:
        abort(500, e)
