# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import unittest
from contextlib import AbstractContextManager
from contextlib import closing
from contextlib import contextmanager
from http.server import HTTPServer
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread

from browser.chrome import remote_chrome
from browser.chrome._chrome import _ChromeVersion
from browser.color import RGBColor
from browser.css_properties import get_background_color
from browser.css_properties import get_borders_style
from browser.css_properties import get_text_color
from browser.css_properties import get_visible_color
from browser.css_properties import get_width
from browser.html_elements import Button
from browser.html_elements import HyperLink
from browser.html_elements import Img
from browser.html_elements import InputField
from browser.html_elements import PreFormattedText
from browser.html_elements import Table
from browser.html_elements import Video
from browser.html_elements import VisibleElement
from browser.webdriver import AttributeNotFound
from browser.webdriver import Browser
from browser.webdriver import ByCSS
from browser.webdriver import ByXPATH
from browser.webdriver import CursorStyle
from browser.webdriver import ElementClickIntercepted
from browser.webdriver import ElementNotFound
from browser.webdriver import ElementNotInteractable
from browser.webdriver import Keys
from browser.webdriver import MultipleElementsFound
from browser.webdriver import StaleElementReference
from browser.webdriver import get_visible_text


@contextmanager
def _current_directory_served_http() -> AbstractContextManager[str]:
    serve_directory = str(Path(__file__).parent)
    http_server = HTTPServer(
        ('127.0.0.1', 0),
        lambda r, c, s: SimpleHTTPRequestHandler(r, c, s, directory=serve_directory),
        )
    [listen_host, listen_port] = http_server.server_address
    thread = Thread(target=http_server.serve_forever, kwargs={'poll_interval': 0.5}, daemon=True)
    thread.start()
    try:
        yield f'http://{listen_host}:{listen_port}/'
    finally:
        http_server.shutdown()
        thread.join()
        # Wait server socket to be closed to prevent "ResourceWarning" errors in logs.
        http_server.server_close()


@contextmanager
def _opened_page(page_file: str) -> AbstractContextManager[Browser]:
    with _current_directory_served_http() as server_url:
        with _remote_page(server_url + page_file) as browser:
            yield browser


@contextmanager
def _remote_page(url: str) -> AbstractContextManager[Browser]:
    with closing(remote_chrome("http://127.0.0.1:9515")) as browser:
        browser.open(url)
        yield browser


class TestChrome(unittest.TestCase):

    def test_title(self):
        with _opened_page('test_title.html') as browser:
            title = browser.get_title()
            self.assertEqual(title, 'PAGE_TITLE')

    def test_href(self):
        with _opened_page('test_href.html') as browser:
            selector = ByXPATH.quoted("//a[@class=%s]", 'irrelevant-class')
            hyperlink = HyperLink(browser.wait_element(selector, 1))
            text = hyperlink.get_text()
            self.assertEqual(text, "Irrelevant href")

    def test_href_get_full_url(self):
        expected_absolute_url = "http://irrelevanthost.irrelevantdomain/irrelevant/absolute/path"
        with _opened_page('test_href_get_full_url.html') as browser:
            absolute_hyperlink = HyperLink(browser.wait_element(ByCSS("#absolute"), 1))
            url_with_absolute_path = absolute_hyperlink.get_full_url()
            relative_hyperlink = HyperLink(browser.wait_element(ByCSS("#relative"), 1))
            url_with_relative_path = relative_hyperlink.get_full_url()
            self.assertEqual(url_with_absolute_path, expected_absolute_url)
            self.assertTrue(url_with_relative_path.startswith("http"))
            self.assertTrue(url_with_relative_path.endswith("/irrelevant/relative/path"))

    def test_button_get_text(self):
        with _opened_page('test_button_get_text.html') as browser:
            button = Button(browser.wait_element(ByXPATH("//button[@id='submit']"), 1))
            button_name = button.get_text()
            self.assertEqual(button_name, "IRRELEVANT")

    def test_cursor_state(self):
        with _opened_page('test_cursor_state.html') as browser:
            button = Button(browser.wait_element(ByXPATH("//button[@id='submit']"), 1))
            button_style = button.get_cursor_style()
            self.assertEqual(button_style, CursorStyle.NOT_ALLOWED)

    def test_button_mouse_click(self):
        with _opened_page('test_button_mouse_click.html') as browser:
            mouse_pointer = browser.request_mouse()
            selector = ByCSS("#disable-me")
            button = Button(browser.wait_element(selector, 1))
            mouse_pointer.click(button.get_bounding_rect().get_absolute_coordinates(0.5, 0.5))
            self.assertFalse(button.is_active())

    def test_non_existing_element(self):
        with _opened_page('test_non_existing_element.html') as browser:
            with self.assertRaises(ElementNotFound):
                browser.wait_element(ByCSS(".NONEXISTENT"), 0)

    def test_input_get_text(self):
        with _opened_page('test_input_get_text.html') as browser:
            selector = ByCSS('#id-search-field')
            search_field = InputField(browser.wait_element(selector, 1))
            empty_text = search_field.get_text()
            self.assertEqual(empty_text, "")

    def test_input_is_active(self):
        with _opened_page('test_input_is_active.html') as browser:
            active_selector = ByCSS('#active-input')
            inactive_selector = ByCSS('#inactive-input')
            active_input = InputField(browser.wait_element(active_selector, 1))
            inactive_input = InputField(browser.wait_element(inactive_selector, 1))
            self.assertTrue(active_input.is_active())
            self.assertFalse(inactive_input.is_active())

    def test_mouse_hover(self):
        with _opened_page('test_mouse_hover.html') as browser:
            mouse_pointer = browser.request_mouse()
            selector = ByCSS("#hover-over")
            popup_area = VisibleElement(browser.wait_element(selector, 1))
            mouse_pointer.hover(popup_area.get_bounding_rect().get_absolute_coordinates(0.5, 0.5))
            browser.wait_element(ByXPATH("//span[@id='myPopup']"), 1).invoke()

    def test_search_keypress(self):
        with _opened_page('test_search_keypress.html') as browser:
            search_field_selector = ByCSS("#id-search-field")
            search_field = InputField(browser.wait_element(search_field_selector, 1))
            search_field.invoke()
            search_text = "IRRELEVANT"
            keyboard = browser.request_keyboard()
            keyboard.send_keys(search_text)
            keyboard.send_keys(Keys.ENTER)
            result_selector = ByXPATH("//div[@id='input-result']")
            search_result = browser.wait_element(result_selector, 1)
            result_text = get_visible_text(search_result)
            self.assertEqual(search_text, result_text)

    def test_stale_element(self):
        with _opened_page('test_stale_element.html') as browser:
            search_field_selector = ByCSS("#id-search-field")
            search_field = InputField(browser.wait_element(search_field_selector, 1))
            browser.refresh()
            with self.assertRaises(StaleElementReference):
                search_field.invoke()
            with self.assertRaises(StaleElementReference):
                search_field.get_text()

    def test_tab_lifecycle(self):
        with _opened_page('test_tab_lifecycle.html') as browser:
            current_url = browser.get_current_url()
            first_tab = browser.get_current_tab()
            search_selector = ByCSS("#id-search-field")
            browser.wait_element(search_selector, 1)
            second_tab = browser.open_in_tab(current_url + '?second_tab=true')
            self.assertEqual(len(browser.get_tabs()), 2)
            browser.wait_element(search_selector, 1)
            current_url = browser.get_current_url()
            self.assertIn('second_tab', current_url)
            first_tab.switch_to()
            second_tab.close()
            self.assertEqual(len(browser.get_tabs()), 1)
            current_url = browser.get_current_url()
            self.assertNotIn('second_tab', current_url)

    def test_get_url(self):
        with _opened_page('test_get_url.html') as browser:
            initial_url = browser.get_current_url()
            search_selector = ByCSS("#id-search-field")
            search_field = InputField(browser.wait_element(search_selector, 1))
            search_field.invoke()
            search_text = "IRRELEVANT"
            keyboard = browser.request_keyboard()
            keyboard.send_keys(search_text)
            keyboard.send_keys(Keys.ENTER)
            search_result = InputField(browser.wait_element(search_selector, 1))
            result_text = search_result.get_value()
            self.assertEqual(search_text, result_text)
            after_search_url = browser.get_current_url()
            self.assertIn("query=IRRELEVANT", after_search_url)
            self.assertTrue(after_search_url.startswith(initial_url))

    def test_get_sub_element(self):
        with _opened_page('test_get_sub_element.html') as browser:
            outer_box = browser.wait_element(ByCSS("#outer-box"), 1)
            inner_box = ByXPATH(".//div[@id='inner-box']").find_in(outer_box)
            text = get_visible_text(inner_box)
            self.assertEqual(text, "TEXT")

    def test_stale_reference_sub_element(self):
        with _opened_page('test_stale_reference_sub_element.html') as browser:
            navigation_bar = browser.wait_element(ByCSS("#outer-box"), 1)
            browser.refresh()
            with self.assertRaises(StaleElementReference):
                ByXPATH(".//div[@id='inner-box']").find_in(navigation_bar)

    def test_get_existing_sub_elements(self):
        with _opened_page('test_existing_sub_elements.html') as browser:
            parent_element = browser.wait_element(ByCSS("#outer-box"), 1)
            children = ByXPATH(".//li").find_all_in(parent_element)
            self.assertGreater(len(children), 0)

    def test_get_non_existing_sub_elements(self):
        with _opened_page('test_get_non_existing_sub_elements.html') as browser:
            parent_element = browser.wait_element(ByCSS("#outer-box"), 1)
            children = ByXPATH(".//NONEXISTING").find_all_in(parent_element)
            self.assertEqual(len(children), 0)

    def test_table(self):
        with _opened_page('test_table.html') as browser:
            feature_table = Table(browser.wait_element(ByCSS("#uneven-table"), 1))
            column_names = feature_table.get_columns()
            self.assertEqual(len(column_names), 2)
            [first_row, long_row, short_row, last_row] = feature_table.get_non_empty_rows()
            self.assertEqual(len(first_row), 2)
            self.assertEqual(len(long_row), 3)
            self.assertEqual(len(short_row), 1)
            self.assertEqual(len(last_row), 2)

    def test_active_element(self):
        with _opened_page('test_active_element.html') as browser:
            switch = Button(browser.wait_element(ByCSS("#switch"), 1))
            deactivable_button = Button(browser.wait_element(ByCSS("#deactivable-button"), 1))
            self.assertTrue(deactivable_button.is_active())
            switch.invoke()
            self.assertFalse(deactivable_button.is_active())
            switch.invoke()
            self.assertTrue(deactivable_button.is_active())

    def test_get_text_color(self):
        with _opened_page('test_get_text_color.html') as browser:
            red_text_label = browser.wait_element(ByXPATH("//label[@id='red']"), 1)
            red_text_color = get_text_color(red_text_label)
            blue_text_label = browser.wait_element(ByXPATH("//label[@id='blue']"), 1)
            blue_text_color = get_text_color(blue_text_label)
            red = RGBColor(255, 0, 0)
            blue = RGBColor(0, 0, 255)
            self.assertTrue(red_text_color.is_shade_of(red))
            self.assertTrue(blue_text_color.is_shade_of(blue))

    def test_get_background_color(self):
        with _opened_page('test_get_background_color.html') as browser:
            blue_element = browser.wait_element(ByXPATH("//div[@id='blue-background']"), 1)
            blue_text_color = get_background_color(blue_element)
            red_element = browser.wait_element(ByXPATH("//div[@id='red-background']"), 1)
            red_text_color = get_background_color(red_element)
            blue = RGBColor(0, 0, 255)
            red = RGBColor(255, 0, 0)
            self.assertTrue(blue_text_color.is_shade_of(blue))
            self.assertTrue(red_text_color.is_shade_of(red))

    def test_get_width(self):
        with _opened_page('test_get_width.html') as browser:
            fixed_length_field = browser.wait_element(ByCSS("#fixed-width"), 1)
            variable_length_field = browser.wait_element(ByCSS("#variable-width"), 1)
            fixed_length = get_width(fixed_length_field)
            variable_length = get_width(variable_length_field)
            self.assertEqual(fixed_length, 100.0)
            self.assertGreater(variable_length, 0.0)

    def test_input_field(self):
        with _opened_page('test_input_field.html') as browser:
            search_selector = ByCSS("#id-search-field")
            search_field = InputField(browser.wait_element(search_selector, 1))
            initial_text = search_field.get_value()
            self.assertEqual(initial_text, '')
            search_text = "IRRELEVANT"
            search_field.put(search_text)
            changed_text = search_field.get_value()
            self.assertEqual(changed_text, search_text)
            search_field.clear()
            empty_text = search_field.get_value()
            self.assertEqual(empty_text, '')

    def test_scroll_to_bottom(self):
        with _opened_page('test_scroll_to_bottom.html') as browser:
            browser.scroll_to_bottom()
            # TODO: Assert if page is scrolled

    def test_borders_style(self):
        with _opened_page('test_borders_style.html') as browser:
            four_colors_element = browser.wait_element(ByCSS("#four-colors"), 1)
            three_colors_element = browser.wait_element(ByCSS("#three-colors"), 1)
            two_colors_element = browser.wait_element(ByCSS("#two-colors"), 1)
            single_color_element = browser.wait_element(ByCSS("#single-color"), 1)
            four_colors_style = get_borders_style(four_colors_element)
            three_colors_style = get_borders_style(three_colors_element)
            two_colors_style = get_borders_style(two_colors_element)
            single_color_style = get_borders_style(single_color_element)
            black = RGBColor(0, 0, 0)
            red = RGBColor(255, 0, 0)
            green = RGBColor(0, 255, 0)
            blue = RGBColor(0, 0, 255)
            self.assertFalse(any(map(four_colors_style.is_encircled_by, [black, red, green, blue])))
            self.assertFalse(any(map(three_colors_style.is_encircled_by, [black, red, green, blue])))
            self.assertFalse(any(map(two_colors_style.is_encircled_by, [black, red, green, blue])))
            self.assertFalse(single_color_style.is_encircled_by(black))
            self.assertTrue(single_color_style.is_encircled_by(red))
            self.assertFalse(single_color_style.is_encircled_by(green))
            self.assertFalse(single_color_style.is_encircled_by(blue))

    def test_focus(self):
        with _opened_page('test_focus.html') as browser:
            arbitrary_element = VisibleElement(browser.wait_element(ByCSS("#to-focus"), 1))
            self.assertFalse(arbitrary_element.is_focused())
            arbitrary_element.invoke()
            self.assertTrue(arbitrary_element.is_focused())

    def test_get_string_property(self):
        with _opened_page('test_get_string_property.html') as browser:
            element = browser.wait_element(ByCSS("#irrelevant"), 1)
            element_type_attribute = element.get_dom_string_property("type")
            self.assertEqual(element_type_attribute, "email")
            with self.assertRaisesRegex(RuntimeError, "does not contain property"):
                element.get_dom_string_property("non-existing-property")
            with self.assertRaisesRegex(RuntimeError, "is not str"):
                element.get_dom_string_property("readOnly")

    def test_get_bool_property(self):
        with _opened_page('test_get_bool_property.html') as browser:
            element = browser.wait_element(ByCSS("#irrelevant"), 1)
            is_checked = element.get_dom_bool_property("checked")
            self.assertTrue(is_checked)
            with self.assertRaisesRegex(RuntimeError, "does not contain property"):
                element.get_dom_bool_property("non-existing-property")
            with self.assertRaisesRegex(RuntimeError, "is not bool"):
                element.get_dom_bool_property("type")

    def test_get_attribute(self):
        with _opened_page('test_get_attribute.html') as browser:
            element_with_class = browser.wait_element(ByCSS("#with-class"), 1)
            class_attribute = element_with_class.get_attribute("class")
            self.assertEqual(class_attribute, "irrelevant")
            element_without_class = browser.wait_element(ByCSS("#without-class"), 1)
            with self.assertRaises(AttributeNotFound):
                element_without_class.get_attribute("class")

    def test_video(self):
        with _opened_page('test_get_video_source.html') as browser:
            single_source = Video(browser.wait_element(ByCSS("#tag-source"), 1))
            self.assertTrue(single_source.is_paused())
            [single_url] = single_source.get_sources()
            self.assertRegex(single_url, "http://.*/first_source.mp4")
            multiple_videos_source = Video(browser.wait_element(ByCSS("#videos-source"), 1))
            [first_url, second_url] = multiple_videos_source.get_sources()
            self.assertRegex(first_url, "http://.*/second_source.mp4")
            self.assertRegex(second_url, "http://.*/third_source.mp4")
            mixed_videos_source = Video(browser.wait_element(ByCSS("#mixed-source"), 1))
            [first_url, second_url, third_url] = mixed_videos_source.get_sources()
            self.assertRegex(first_url, "http://.*/first_source.mp4")
            self.assertRegex(second_url, "http://.*/second_source.mp4")
            self.assertRegex(third_url, "http://.*/third_source.mp4")
            sourceless_element = Video(browser.wait_element(ByCSS("#sourceless"), 1))
            empty_sources = sourceless_element.get_sources()
            self.assertEqual(empty_sources, [])

    def test_input_is_readonly(self):
        with _opened_page('test_input_is_readonly.html') as browser:
            active_selector = ByCSS('#active-input')
            readonly_selector = ByCSS('#readonly-input')
            active_input = InputField(browser.wait_element(active_selector, 1))
            readonly_input = InputField(browser.wait_element(readonly_selector, 1))
            self.assertTrue(readonly_input.is_readonly())
            self.assertFalse(active_input.is_readonly())

    def test_pre_get_text(self):
        with _opened_page('test_pre_get_text.html') as browser:
            selector = ByCSS('#pre-formatted-text')
            text_element = PreFormattedText(browser.wait_element(selector, 1))
            text = text_element.get_raw_text()
            self.assertIn('Tab follows: "\t"', text)
            self.assertIn('No-break space follows: "\N{NO-BREAK SPACE}"', text)
            self.assertIn('Multiple line breaks follows: "\n\n"', text)
            self.assertIn('Irrelevant hyperlink', text)

    def test_drag_n_drop(self):
        with _opened_page('test_drag_n_drop.html') as browser:
            draggable_selector = ByXPATH("//div[@id='draggable']")
            dropzone_selector = ByXPATH("//div[@id='dropzone']")
            draggable_element = VisibleElement(browser.wait_element(draggable_selector, 1))
            dropzone_element = VisibleElement(browser.wait_element(dropzone_selector, 1))
            mouse_pointer = browser.request_mouse()
            mouse_pointer.drag_n_drop(
                draggable_element.get_bounding_rect().get_absolute_coordinates(0.25, 0.25),
                dropzone_element.get_bounding_rect().get_absolute_coordinates(0.25, 0.33),
                )
            dropzone_rect = dropzone_element.get_bounding_rect()
            draggable_rect_1 = draggable_element.get_bounding_rect()
            self.assertTrue(dropzone_rect.contains(draggable_rect_1))
            mouse_pointer.drag_n_drop(
                draggable_element.get_bounding_rect().get_absolute_coordinates(0.5, 0.5),
                dropzone_element.get_bounding_rect().get_absolute_coordinates(0.66, 0.75),
                )
            draggable_rect_2 = draggable_element.get_bounding_rect()
            self.assertTrue(dropzone_rect.contains(draggable_rect_2))

    def test_ambiguous_selector(self):
        ambiguous_xpath = "//div[contains(@class, 'container')]/input[contains(@class, 'search')]"
        with _opened_page('test_ambiguous_selector.html') as browser:
            with self.assertRaises(MultipleElementsFound):
                browser.wait_element(ByXPATH(ambiguous_xpath), 1)
            container_element = browser.wait_element(ByXPATH("//div[@id='outer-container']"), 1)
            with self.assertRaises(MultipleElementsFound):
                ByXPATH(".//input[contains(@class, 'search')]").find_in(container_element)

    def test_interact_hidden(self):
        with _opened_page('test_interact_hidden.html') as browser:
            selector = ByXPATH("//input[@id='hidden-input']")
            hidden_input = InputField(browser.wait_element(selector, 1))
            with self.assertRaises(ElementNotInteractable):
                hidden_input.invoke()
            with self.assertRaises(ElementNotInteractable):
                hidden_input.put("something")
            existing_text = hidden_input.get_value()
            self.assertEqual(existing_text, "Hidden value")

    def test_image_capture(self):
        with _opened_page('test_image_capture.html') as browser:
            selector = ByXPATH("//div[contains(@class, 'blue-background')]")
            blue_element = VisibleElement(browser.wait_element(selector, 1))
            image = blue_element.get_image_bytes()
            self.assertTrue(_is_png(image))

    def test_img(self):
        with _opened_page('test_img.html') as browser:
            selector = ByXPATH("//img[@id='image']")
            image = Img(browser.wait_element(selector, 1))
            [width, height] = image.get_dimensions_px()
            self.assertTrue(isinstance(width, int))
            self.assertTrue(isinstance(height, int))

    def test_click_intercepted(self):
        with _opened_page('test_click_intercepted.html') as browser:
            selector = ByXPATH('//a')
            link = HyperLink(browser.wait_element(selector, 1))
            with self.assertRaises(ElementClickIntercepted):
                link.invoke()

    def test_get_visible_color(self):
        expected_color = RGBColor(128, 64, 64)
        with _opened_page('test_get_visible_color.html') as browser:
            inner_square = browser.wait_element(ByXPATH('//div[@id="inner"]'), 1)
            inner_square_color = get_visible_color(inner_square)
            self.assertTrue(inner_square_color.is_shade_of(expected_color))


def _is_png(raw: bytes) -> bool:
    png_signature = b'\x89PNG\x0d\x0a\x1a\x0a'
    return raw.startswith(png_signature)


class TestChromeVersion(unittest.TestCase):

    def test_complete_match(self):
        chrome_driver_version = _ChromeVersion(
            "119.0.6045.159 "
            "(eaa767197fa7dd412133d1b84f7eb60da43409c9-refs/branch-heads/6045@{#1327})")
        browser_version = _ChromeVersion("119.0.6045.159")
        self.assertTrue(chrome_driver_version.is_compatible_with(browser_version))
        self.assertTrue(browser_version.is_compatible_with(chrome_driver_version))

    def test_match_without_patch_field(self):
        chrome_driver_version = _ChromeVersion(
            "119.0.6045.999 "
            "(eaa767197fa7dd412133d1b84f7eb60da43409c9-refs/branch-heads/6045@{#1327})")
        browser_version = _ChromeVersion("119.0.6045.000")
        self.assertTrue(chrome_driver_version.is_compatible_with(browser_version))
        self.assertTrue(browser_version.is_compatible_with(chrome_driver_version))

    def test_mismatch(self):
        chrome_driver_version = _ChromeVersion(
            "118.0.5993.70 "
            "(e52f33f30b91b4ddfad649acddc39ab570473b86-refs/branch-heads/5993@{#1216}")
        browser_version = _ChromeVersion("119.0.6045.159")
        self.assertFalse(chrome_driver_version.is_compatible_with(browser_version))
        self.assertFalse(browser_version.is_compatible_with(chrome_driver_version))


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
