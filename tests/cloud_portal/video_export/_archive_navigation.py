# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Collection
from typing import List
from typing import Optional
from typing import Sequence

from browser.color import RGBColor
from browser.html_elements import Button
from browser.media_capturing import ImageCapture
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import VisibleElement

_logger = logging.getLogger(__name__)


class _ColoredChunk:

    def __init__(self, start: int, end: int, color: RGBColor):
        self.color = color
        self.start = start
        self.end = end

    def concatenate(self, other: '_ColoredChunk') -> None:
        if self.start - other.end > 1 or other.start - self.end > 1:
            raise ValueError(f"{self}: {other} is not adjacent")
        elif self.end < other.start:
            self.end = other.end
        elif other.end < self.start:
            self.start = other.start
        else:
            raise RuntimeError(f"{self}: Can't concatenate {other}")

    def extend(self) -> None:
        self.end += 1

    def right_neighbor(self, color: RGBColor) -> '_ColoredChunk':
        return self.__class__(self.end, self.end + 1, color)

    def get_length(self) -> int:
        return self.end - self.start

    def __repr__(self):
        return f'{self.__class__}({self.start}, {self.end}, {self.color})'


class Timeline:

    def __init__(self, browser: Browser):
        self._browser = browser

    def _get_element(self) -> VisibleElement:
        return VisibleElement(self._browser.wait_element(ByXPATH('//nx-timeline-selection'), 10))

    def select_relative_part(self, rel_start: float = 0, rel_end: float = 1) -> None:
        if not 0 <= rel_start <= rel_end <= 1:
            raise RuntimeError(
                f"Expected 0 <= rel_start <= rel_end <= 1; "
                f"Received rel_start={rel_start}, rel_end={rel_end}")
        element = self._get_element()
        mouse = self._browser.request_mouse()
        mouse.drag_n_drop(
            element.get_bounding_rect().get_absolute_coordinates(rel_start, 0.0),
            element.get_bounding_rect().get_absolute_coordinates(rel_end, 0.0),
            pause_after_action_ms=1000,  # Web interface response is slow.
            )

    def get_archive_chunk_sequence(self) -> 'ColoredChunkSequence':
        _logger.info('%r: Looking for archive chunks', self)
        image_bytes = self._get_element().get_image_bytes()
        image_capture = ImageCapture.from_bytes(image_bytes)
        # Take 1 pixel thin strip.
        archive_strip = image_capture.crop(
            0,
            image_capture.get_width(),
            int(image_capture.get_height() * 0.5),
            int(image_capture.get_height() * 0.5) + 1,
            )
        # Find all archive chunks as continuous pieces of colorful pixels.
        # Colors of tooltip are slightly different while running locally and in VM.
        timeline_tooltip_colors = [RGBColor(225, 231, 234), RGBColor(229, 233, 235)]
        chunked_stripe = _make_stripe(archive_strip.get_row_colors(row_n=0))
        cleaned_chunked_stripe = chunked_stripe
        for tooltip_color in timeline_tooltip_colors:
            cleaned_chunked_stripe = cleaned_chunked_stripe.dissolve(tooltip_color)
        # Colors of archive are slightly different while running locally and in VM.
        archive_color_first = RGBColor(76, 188, 40)
        archive_color_second = RGBColor(70, 145, 14)
        archive_color_third = RGBColor(82, 143, 51)
        chunks = cleaned_chunked_stripe.filter_by_colors(
            [archive_color_first, archive_color_second, archive_color_third])
        _logger.info('%r: Archive chunks: %s', self, chunks)
        return chunks

    def get_play_button(self) -> Button:
        locator = '//nx-system-view-camera-page//nx-playback-controls//svg-icon[contains(@data-src, "play.svg")]'
        return Button(self._browser.wait_element(ByXPATH(locator), 10))

    def get_pause_button(self) -> Button:
        locator = '//nx-system-view-camera-page//nx-playback-controls//svg-icon[contains(@data-src, "pause.svg")]'
        return Button(self._browser.wait_element(ByXPATH(locator), 10))


class ColoredChunkSequence:

    def __init__(self, chunks: Sequence[_ColoredChunk]):
        if not chunks:
            raise ValueError("Chunk sequence must at least one chunks long")
        self._chunks = chunks

    def dissolve(self, color: RGBColor) -> 'ColoredChunkSequence':
        result: List[_ColoredChunk] = []
        for chunk in self._chunks:
            try:
                last_chunk = result[-1]
            except IndexError:
                if chunk.color != color:
                    result.append(chunk)
                continue
            if chunk.color == color or chunk.color == last_chunk.color:
                last_chunk.concatenate(chunk)
            else:
                result.append(chunk)
        if self._chunks[0].color == color:
            result[0].concatenate(self._chunks[0])
        return self.__class__(result)

    def filter_by_colors(self, colors: Collection[RGBColor]) -> 'ColoredChunkSequence':
        chunks = []
        for chunk in self._chunks:
            _logger.debug("Actual color: %s, expected colors: %s", chunk.color, colors)
            if chunk.color in colors:
                chunks.append(chunk)
        return self.__class__(chunks)

    def get_length(self) -> int:
        return len(self._chunks)

    def get_first(self) -> Optional['_ColoredChunk']:
        return self._chunks[0]

    def get_last(self) -> Optional['_ColoredChunk']:
        return self._chunks[-1]


class TimelineSelectionActionPanel:

    def __init__(self, browser: Browser):
        self._browser = browser

    def start_export(self) -> None:
        selector = ByXPATH(
            '//nx-timeline-selection-action-panel/a[contains(@class, "export-link")]')
        Button(self._browser.wait_element(selector, 5)).invoke()


def _make_stripe(colors: Sequence[RGBColor]) -> ColoredChunkSequence:
    if not colors:
        raise ValueError("Color sequence must be at least one pixel long")
    [first_color, *other_colors] = colors
    result = [_ColoredChunk(0, 0, first_color)]
    for color in other_colors:
        last_chunk = result[-1]
        if last_chunk.color == color:
            last_chunk.extend()
        else:
            result.append(last_chunk.right_neighbor(color))
    return ColoredChunkSequence(result)
