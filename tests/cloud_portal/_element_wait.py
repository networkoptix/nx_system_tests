# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Any
from typing import Callable

from browser.webdriver import ElementNotFound


def element_is_present(raises_element_not_found: Callable[[], Any]) -> bool:
    try:
        raises_element_not_found()
    except ElementNotFound:
        return False
    return True
