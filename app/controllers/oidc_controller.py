from urllib.parse import urlencode
from urllib.parse import urljoin

from flask import abort
from flask import redirect

from app.models.platform_config import LTIPlatform
from app.models.platform_config import LTIPlatformStorage
from app.models.state import LTIState
from app.models.state import LTIStateStorage


def login(request):
    pass