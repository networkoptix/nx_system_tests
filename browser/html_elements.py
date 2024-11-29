# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
# See: https://www.w3schools.com/tags/
from pathlib import Path
from typing import Mapping
from typing import Sequence

from browser.color import RGBColor
from browser.css_properties import BordersStyle
from browser.css_properties import get_borders_style
from browser.css_properties import get_text_color
from browser.webdriver import AttributeNotFound
from browser.webdriver import ByXPATH
from browser.webdriver import PropertyNotFound
from browser.webdriver import VisibleElement
from browser.webdriver import WebDriverElement


class InputField(VisibleElement):

    def get_value(self) -> str:
        return self._webdriver_element.get_dom_string_property('value')

    def put(self, text: str):
        data = {"text": text, "value": list(text)}
        result = self._webdriver_element.http_post("/value", data)
        if result is not None:
            raise RuntimeError(f"Unexpected value: {result}")

    def clear(self):
        script = Path(__file__).with_name('clear_value.js').read_text()
        self._webdriver_element.execute_javascript_function(script)

    def is_active(self) -> bool:
        return self._webdriver_element.http_get('enabled')

    def is_readonly(self) -> bool:
        try:
            self._webdriver_element.get_attribute('readonly')
        except AttributeNotFound:
            return False
        return True

    def get_border_style(self) -> BordersStyle:
        return get_borders_style(self._webdriver_element)

    def get_text_color(self) -> RGBColor:
        return get_text_color(self._webdriver_element)


class Button(VisibleElement):

    def is_active(self) -> bool:
        return self._webdriver_element.http_get('enabled')


class HyperLink(VisibleElement):

    def is_active(self) -> bool:
        return self._webdriver_element.http_get("enabled")

    def get_full_url(self) -> str:
        return self._webdriver_element.get_dom_string_property("href")


# See: https://html.spec.whatwg.org/multipage/tables.html#the-table-element
class Table(VisibleElement):

    def get_columns(self) -> Sequence[WebDriverElement]:
        return ByXPATH("thead/tr/th").find_all_in(self._webdriver_element)

    def get_non_empty_rows(self) -> Sequence[Sequence[WebDriverElement]]:
        # JavaScript-based request is used to make the method atomic to decrease StaleReference
        # error probability by making requesting cells via single HTTP request, what is impossible
        # to achieve via any standard selector strategy.
        script = Path(__file__).with_name('table_get_rows.js').read_text()
        matrix: Sequence[Sequence[Mapping[str, str]]]
        matrix = self._webdriver_element.execute_javascript_function(script)
        return [[self._webdriver_element.get_child(cell) for cell in row] for row in matrix]


class Video(VisibleElement):

    def get_sources(self) -> Sequence[str]:
        result = []
        if src_tag := self._get_src_tag():
            result.append(src_tag)
        result.extend(self._get_source_elements())
        return result

    def is_paused(self) -> bool:
        return self._webdriver_element.get_dom_bool_property('paused')

    def _get_src_tag(self) -> str:
        try:
            return self._webdriver_element.get_dom_string_property("src")
        except PropertyNotFound:
            return ''

    def _get_source_elements(self) -> Sequence[str]:
        result = []
        for video_source_element in ByXPATH("./source").find_all_in(self._webdriver_element):
            result.append(video_source_element.get_dom_string_property("src"))
        return result


class PreFormattedText(VisibleElement):

    def get_raw_text(self) -> str:
        return self._webdriver_element.get_dom_string_property("textContent")


class Img(VisibleElement):

    def get_dimensions_px(self) -> tuple[int, int]:
        # Img tag has its own 'width' and 'height' attributes,
        # but they can't be obtained atomically via single call.
        # See: https://www.w3schools.com/tags/tag_img.asp
        raw_rect = self._webdriver_element.http_get("/rect")
        width = raw_rect['width']
        height = raw_rect['height']
        # It is not specified, but it seems that picture couldn't have sub-pixel dimensions.
        if not isinstance(width, int):
            raise RuntimeError(f"Got non integer width {width}")
        if not isinstance(height, int):
            raise RuntimeError(f"Got non integer height {height}")
        return raw_rect['width'], raw_rect['height']
