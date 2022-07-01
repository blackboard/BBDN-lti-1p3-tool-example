from flask import make_response

from app.models.tool_config import LTITool
from app.models.tool_config import LTIToolStorage


def jwks():
    _jwk = LTITool(LTIToolStorage()).jwks
    r = make_response(_jwk, 200)
    r.headers.add_header("Content-Type", "application/json; utf-8")
    return r
