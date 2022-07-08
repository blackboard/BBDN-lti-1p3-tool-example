from flask import abort

from app.controllers import launch_controller
from app.models.jwt import LTIJwtPayload
from app.models.state import LTIStateStorage, LTIState
from app.models.tool_config import LTITool
from app.models.tool_config import LTIToolStorage
from app.utility.token_client import TokenClient


def authcode(request):
    pass
