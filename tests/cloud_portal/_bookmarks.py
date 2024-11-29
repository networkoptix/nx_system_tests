# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from datetime import datetime
from typing import Sequence

from browser.html_elements import Button
from browser.html_elements import InputField
from browser.html_elements import Video
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import ElementSelector
from browser.webdriver import StaleElementReference
from browser.webdriver import VisibleElement
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class _BookmarkInfo(VisibleElement):

    def get_naive_start(self) -> datetime:
        """Timezone is not specified on the web page, so we can only return naive datetime."""
        xpath = ".//span[@class='bookmarks-info-timestamp']//span"
        [date_element, time_element] = ByXPATH(xpath).find_all_in(self._webdriver_element)
        date_as_str = get_visible_text(date_element)
        time_as_str = get_visible_text(time_element)
        return datetime.strptime(
            f'{date_as_str}; {time_as_str}',
            '%b %d, %Y; %I:%M %p',
            )

    def get_bookmark_name(self) -> str:
        name_element = ByXPATH(
            ".//nx-ml-ellipsis//div[@class='body']").find_in(self._webdriver_element)
        return get_visible_text(name_element)

    def get_camera_name(self) -> str:
        name_element = ByXPATH(
            ".//p[@class='bookmarks-info-name']").find_in(self._webdriver_element)
        return get_visible_text(name_element)


class _BookmarkThumbnail:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def get_info(self) -> _BookmarkInfo:
        info_element = ByXPATH(
            ".//div[@class='bookmarks-info']").find_in(self._element)
        return _BookmarkInfo(info_element)


class BookmarksComponent:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def open_bookmark(self, bookmark_name: str) -> None:
        selector = ByXPATH.quoted(
            '//nx-bookmarks-component//nx-bookmarks-card//'
            'nx-ml-ellipsis[contains(@class, "bookmarks-info-title")]//div[contains(text(), %s)]',
            bookmark_name,
            )
        self._browser.wait_element(selector, 10).invoke()

    def list_bookmark_thumbnails(self) -> Sequence[_BookmarkThumbnail]:
        table = None
        table_selector = ByXPATH("//nx-bookmarks-component/div/div[@class='body']/div")
        for _ in range(2):
            self._refresh_bookmark_thumbnails()
            try:
                table = self._browser.wait_element(table_selector, 5)
            except ElementNotFound:
                continue
        if table is None:
            return []
        thumbnail_elements = ByXPATH(".//nx-bookmarks-card").find_all_in(table)
        return [_BookmarkThumbnail(t) for t in thumbnail_elements]

    def _refresh_bookmark_thumbnails(self) -> None:
        selector = ByXPATH(
            "//nx-bookmarks-component//nx-alert-block//div[@class='card--body-content']//button")
        try:
            button = self._browser.wait_element(selector, 2)
        except ElementNotFound:
            _logger.debug("Refresh button not found, bookmark thumbnails not refreshed")
            return
        _logger.debug("Refreshing bookmark thumbnails")
        button.invoke()


class BookmarkDialog:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_download_button(self) -> Button:
        text = self._translation_table.tr("DOWNLOAD")
        selector = ByXPATH.quoted(
            '//nx-bookmarks-card-modal//button[contains(text(), %s)]',
            text,
            )
        return Button(self._browser.wait_element(selector, 10))

    def get_view_recording_button(self) -> Button:
        text = self._translation_table.tr("VIEW_FULL_RECORDING")
        selector = ByXPATH.quoted(
            '//nx-bookmarks-card-modal//a[contains(text(), %s)]',
            text,
            )
        return Button(self._browser.wait_element(selector, 10))

    def _video_is_paused(self) -> bool:
        selector = ByXPATH('//nx-bookmarks-card-modal/div//nx-clip/video')
        started_at = time.monotonic()
        while True:
            try:
                return Video(self._browser.wait_element(selector, 5)).is_paused()
            except StaleElementReference:
                if time.monotonic() - started_at > 5:
                    raise
            _logger.info("A stale element ID is received. Waiting for element to be loaded")
            time.sleep(1)

    def wait_for_playing_video(self, timeout: float = 10):
        started_at = time.monotonic()
        while True:
            if not self._video_is_paused():
                return
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(f"Video is not playing after {timeout} seconds")
            time.sleep(1)

    def get_video_format_error(self) -> WebDriverElement:
        text = self._translation_table.tr("VIDEO_FORMAT_ERROR")
        selector = ByXPATH.quoted(
            '//nx-bookmarks-card-modal//nx-player-placeholder//span[contains(text(), %s)]',
            text,
            )
        return self._browser.wait_element(selector, 15)

    def close(self) -> None:
        selector = ByXPATH('//nx-bookmarks-card-modal//button[contains(@class,  "close")]')
        self._browser.wait_element(selector, 5).invoke()


class BookmarkDownloadModal:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_title(self) -> str:
        selector = ByXPATH.quoted('//nx-bookmark-download//h1/span')
        return get_visible_text(self._browser.wait_element(selector, 5))

    def get_body_text(self) -> str:
        selector = ByXPATH.quoted('//nx-bookmark-download/div//p')
        return get_visible_text(self._browser.wait_element(selector, 5))

    def get_download_button(self) -> Button:
        text = self._translation_table.tr("DOWNLOAD")
        selector = ByXPATH.quoted(
            '//nx-bookmark-download/div//a//span[contains(text(), %s)]',
            text,
            )
        return Button(self._browser.wait_element(selector, 10))


class QuickSelect:

    def __init__(self, browser, translation_table):
        self._browser = browser
        self._translation_table = translation_table

    def show_last_day(self) -> None:
        self._get_button_by_name(self._translation_table.tr('LAST_DAY')).invoke()

    def show_last_7_days(self) -> None:
        self._get_button_by_name(self._translation_table.tr('LAST_SEVEN_DAYS')).invoke()

    def show_last_30_days(self) -> None:
        self._get_button_by_name(self._translation_table.tr('LAST_THIRTY_DAYS')).invoke()

    def _get_root_element(self) -> WebDriverElement:
        return self._browser.wait_element(
            ByXPATH("//nx-bookmarks-component//div[@class='quick-selects']"), 5)

    def _get_button_by_name(self, name: str) -> WebDriverElement:
        for e in ByXPATH("./button").find_all_in(self._get_root_element()):
            if get_visible_text(e) == name:
                return e
        else:
            raise RuntimeError(f"Unable to find quick select button with name {name}")


class Calendar:

    def __init__(self, browser: Browser):
        self._browser = browser

    def wait_until_exists(self, timeout: float = 20) -> None:
        selector = ByXPATH('//nx-bookmarks-component//nx-date-and-time-filter')
        self._browser.wait_element(selector, timeout)

    def get_current_date(self) -> datetime.date:
        today_element = self._browser.wait_element(
            ByXPATH("//button[./span[contains(@class, 'mat-calendar-body-today')]]"), 5)
        date_label = today_element.get_attribute("aria-label")
        return datetime.strptime(date_label, '%B %d, %Y').date()

    def set_date_range(self, start: datetime, end: datetime) -> None:
        self._select_date(start)
        self._select_date(end)

    def _select_date(self, date: datetime) -> None:
        header_controls = self._browser.wait_element(
            ByXPATH("//div[@class='mat-calendar-header']/div[@class='mat-calendar-controls']"), 5)
        year_and_month_button = ByXPATH(
            ".//button[@aria-label='Choose month and year']").find_in(header_controls)
        year_and_month_button.invoke()
        self._select_year_and_month(date)
        self._select_day_of_month(date)

    def _select_year_and_month(self, date: datetime) -> None:
        year_button_selector = ByXPATH.quoted(
            "//mat-multi-year-view/table/tbody//button[@aria-label=%s]", str(date.year))
        self._browser.wait_element(year_button_selector, 5).invoke()
        month_button_selector = ByXPATH.quoted(
            "//mat-year-view/table/tbody//button[contains(@aria-label, %s)]",
            date.strftime('%B'))
        self._browser.wait_element(month_button_selector, 5).invoke()

    def _select_day_of_month(self, date: datetime) -> None:
        day_button_selector = ByXPATH.quoted(
            "//mat-month-view/table/tbody//button[@aria-label=%s]",
            # Format codes for non zero-padded are platform-dependent. Linux: %-d, Windows: %#d.
            date.strftime(f'%B {date.day}, %Y'))
        self._browser.wait_element(day_button_selector, 5).invoke()


class TimeRange:

    def __init__(self, browser: Browser):
        self._browser = browser

    def set(self, start: datetime, end: datetime) -> None:
        self._get_start_selection().set(start)
        self._get_end_selection().set(end)

    def _get_start_selection(self) -> '_TimeBoundary':
        return _TimeBoundary(
            ByXPATH("//div[@class='time-inputs']//nx-time-selector[@point='start']"),
            self._browser,
            )

    def _get_end_selection(self) -> '_TimeBoundary':
        return _TimeBoundary(
            ByXPATH("//div[@class='time-inputs']//nx-time-selector[@point='end']"),
            self._browser,
            )


class _TimeBoundary:

    def __init__(self, selector: ElementSelector, browser: Browser):
        self._root_selector = selector
        self._browser = browser

    def set(self, time_: datetime) -> None:
        self._clear()
        [hours, minutes, am_pm] = time_.strftime('%I %M %p').split()
        self._set_hours_minutes(hours, minutes)
        if am_pm == 'AM':
            self._set_am()
        elif am_pm == 'PM':
            self._set_pm()
        else:
            raise RuntimeError(f"Unexpected AM/PM literal {am_pm!r}")

    def _get_root_element(self) -> WebDriverElement:
        return self._browser.wait_element(self._root_selector, 5)

    def _set_hours_minutes(self, hours: str, minutes: str) -> None:
        input_ = InputField(ByXPATH("./div/input").find_in(self._get_root_element()))
        input_.put(f'{hours}:{minutes}')

    def _get_am_pm_overlay(self) -> WebDriverElement:
        button = Button(ByXPATH("./button").find_in(self._get_root_element()))
        button.invoke()
        return self._browser.wait_element(
            ByXPATH("//div[@class='cdk-overlay-pane']//div[contains(@class, 'periods-menu')]"), 5)

    def _set_am(self) -> None:
        am_pm_overlay = self._get_am_pm_overlay()
        ByXPATH("./button[@tabindex='0']").find_in(am_pm_overlay).invoke()

    def _set_pm(self) -> None:
        am_pm_overlay = self._get_am_pm_overlay()
        ByXPATH("./button[@tabindex='-1']").find_in(am_pm_overlay).invoke()

    def _clear(self) -> None:
        try:
            clear_button = ByXPATH(
                "./div/button[contains(@class, 'clear-btn')]").find_in(self._get_root_element())
        except ElementNotFound:
            return
        clear_button.invoke()


_logger = logging.getLogger(__name__)
