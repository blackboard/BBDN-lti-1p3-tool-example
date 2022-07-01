from app import wsgi
from tests.app import handle_exception
from tests.app import read_file


def test_flow():

    request_event = read_file("functional_login.json")

    wsgi.application.register_error_handler(Exception, handle_exception)
    response = wsgi.lambda_handler(request_event, {})
    assert response
    assert response["statusCode"] == 200
