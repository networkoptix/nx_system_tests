# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.webdriver import WebDriverElement


class NxCheckbox:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def switch(self):
        self._element.invoke()
