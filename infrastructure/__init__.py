import re


def clean_name(branch: str):
    return re.sub("/", "-", branch)[0:30]
