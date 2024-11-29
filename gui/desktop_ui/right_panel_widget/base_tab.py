# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
from typing import Sequence

from gui.desktop_ui.widget import Widget
from gui.testkit import TestKit


class _RightPanelTab:

    def __init__(self, api: TestKit, ribbon_locator: dict):
        self._ribbon = Widget(api, ribbon_locator)
        self._api = api

    def tile_loaders(self) -> Sequence[Widget]:
        return self._ribbon.find_children({
            "name": "mainWidget",
            "type": "QWidget",
            "visible": 1,
            })


# TODO: Make it a part of some generic tile class. Refactor is required.
# https://networkoptix.atlassian.net/browse/FT-2362
def _remove_html_tags(raw_text: str) -> str:
    r"""Remove HTML tags from string.

    >>> _remove_html_tags("<div><span><br></span></div>")
    ''
    >>> _remove_html_tags("<p>Expected <b>text</b></p>")
    'Expected text'
    >>> _remove_html_tags("<style>.text { color: red; }</style><p>Expected <b>text</b></p>")
    'Expected text'
    >>> _remove_html_tags("<p>Expected <b>text</b></p><style>.text { color: red; }</style>")
    'Expected text'
    >>> _remove_html_tags("<p style=\"margin-top: 12px;\">Expected <b>text</b></p>")
    'Expected text'
    """
    text = re.sub(r'<style.*?>.*?</style>', '', raw_text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text
