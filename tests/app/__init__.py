import json
from pathlib import Path
from typing import Optional

from pytest import fail

PAYLOAD_PATH = Path(__file__).parent.parent.parent.joinpath("payloads")


def handle_exception(e):
    fail(f"Test failed {e}", True)


def read_file(file_name, variables: Optional[dict] = None):
    path = get_file_with_json_extension(file_name)

    # return path.read_text()
    with path.open(mode="r") as f:
        data = f.read()
        if variables is not None:
            for key, value in variables.items():
                data = data.replace(key, value)
        return json.loads(data)


def get_file_with_json_extension(file_name):
    if ".json" in file_name:
        path = PAYLOAD_PATH.joinpath(file_name)
    else:
        path = PAYLOAD_PATH.joinpath(f"{file_name}.json")
    return path
