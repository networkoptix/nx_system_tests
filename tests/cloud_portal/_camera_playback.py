# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from browser.html_elements import Video
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import VisibleElement
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class CameraPlayback:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def wait_for_playing_video(self, timeout: float = 10) -> None:
        selector = ByXPATH("//nx-system-view-camera-page//nx-player//div/video")
        video = Video(self._browser.wait_element(selector, 5))
        started_at = time.monotonic()
        while True:
            if not video.is_paused():
                return
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(f"Video is not playing after {timeout} seconds")
            time.sleep(1)

    def get_playing_camera_name(self) -> str:
        selector = ByXPATH(
            '//nx-system-view-index-page/nx-system-view-camera-page/header//span[@class="name"]')
        element = self._browser.wait_element(selector, 15)
        name_and_res = VisibleElement(element).get_text()
        return ''.join(name_and_res.split()[:-1])
