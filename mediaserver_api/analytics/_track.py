# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Any
from typing import Mapping
from typing import Optional
from uuid import UUID

from mediaserver_api._time_period import TimePeriod
from mediaserver_api.analytics._primitives import BoundingBox
from mediaserver_api.analytics._primitives import NormalizedRectangle

_logger = logging.getLogger(__name__)


class BestShot:

    def __init__(self, raw):
        self._raw = raw

    def _timestamp_ms(self) -> int:
        return int(self._raw['timestampUs']) // 1000

    def rectangle(self):
        coordinates = self._raw['rect']
        # If no best shot coords provided by plugin server set coords to -1: it means full frame
        if all([v == -1 for v in coordinates.values()]):
            return NormalizedRectangle(x=0, y=0, width=1, height=1)
        return NormalizedRectangle(**coordinates)

    def exists(self):
        return self._timestamp_ms() != 0


class Title:

    def __init__(self, raw: Mapping[str, Any]):
        self._raw = raw

    def has_image(self) -> bool:
        return self._raw['hasImage']

    def rectangle(self) -> NormalizedRectangle:
        coordinates = self._raw['rect']
        # If no coordinates provided by plugin, server sets all of them to -1 meaning full frame.
        if all([v == -1 for v in coordinates.values()]):
            return NormalizedRectangle(x=0, y=0, width=1, height=1)
        return NormalizedRectangle(**coordinates)

    def text(self) -> str:
        return self._raw['text']


class AnalyticsTrack:

    def __init__(self, raw_track: Mapping):
        self._raw_track = raw_track

    def track_id(self):
        return UUID(self._raw_track['id'])

    def type_id(self):
        return self._raw_track['objectTypeId']

    def time_period(self):
        start_ms = int(self._raw_track['firstAppearanceTimeUs']) // 1000
        end_ms = int(self._raw_track['lastAppearanceTimeUs']) // 1000
        return TimePeriod.from_start_and_end_ms(start_ms=start_ms, end_ms=end_ms)

    def best_shot(self) -> BestShot:
        return BestShot(self._raw_track['bestShot'])

    def title(self) -> Optional[Title]:
        raw_title = self._raw_track.get('title')
        return None if raw_title is None else Title(raw_title)

    def attributes(self):
        return self._raw_track['attributes']

    def position_sequence(self):
        positions = []
        for position in self._raw_track['objectPositionSequence']:
            positions.append(BoundingBox.from_box_data(**position['boundingBox']))
        return positions

    def pretty_formatted(self) -> str:
        number = ""
        attributes = self._raw_track.get("attributes")
        for attr in attributes:
            if attr["name"] == "Number":
                number = f' {attr["value"]}'
                break
        return f"{self._raw_track['objectTypeId']}{number} - {self.track_id()} - {self.time_period()!r}"
