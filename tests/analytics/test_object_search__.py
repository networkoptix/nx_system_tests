# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod
from contextlib import ExitStack
from typing import Optional

from mediaserver_api import TimePeriod
from mediaserver_api.analytics import AnalyticsTrack
from mediaserver_api.analytics import Rectangle
from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import record_analytics_tracks
from tests.analytics.common import recording_camera
from tests.analytics.common import set_object_streamer_tracks
from tests.infra import Failure


def _prepare_search_result(expected_tracks_list, actual_tracks_list):

    def _get_ids(lst):
        return {track.track_id() for track in lst}

    expected_ids = _get_ids(expected_tracks_list)
    actual_ids = _get_ids(actual_tracks_list)
    if expected_ids == actual_ids:
        return {}
    return {
        "Expected, not found": expected_ids - actual_ids,
        "Found, not expected": actual_ids - expected_ids,
        }


class _TimeSearchInterval(metaclass=ABCMeta):

    def __init__(self, time_period: TimePeriod):
        self._period = time_period

    @abstractmethod
    def contains(self, track: AnalyticsTrack) -> bool:
        pass


class _OldTimeSearchInterval(_TimeSearchInterval):

    def contains(self, track):
        # Mediaserver condition: firstAppearanceTime < endTime AND startTime <= lastAppearanceTime
        first_appearance_in_interval = track.time_period().start_ms < self._period.end_ms
        last_appearance_in_interval = self._period.start_ms <= track.time_period().end_ms
        return first_appearance_in_interval and last_appearance_in_interval


class _TrackStartTimeSearchInterval(_TimeSearchInterval):

    def contains(self, track):
        # Mediaserver condition: startTime <= firstAppearanceTime <= endTime
        return self._period.start_ms <= track.time_period().start_ms <= self._period.end_ms


class _TrackStartEndTimeSearchInterval(_TimeSearchInterval):

    def contains(self, track):
        # Mediaserver condition: startTime <= lastAppearanceTime AND firstAppearanceTime <= endTime.
        return (
            self._period.start_ms <= track.time_period().end_ms
            and track.time_period().start_ms <= self._period.end_ms
            )


def _time_interval_search_errors(api, all_tracks, time_search_interval_cls):
    start_track_idx = len(all_tracks) // 8
    end_track_idx = start_track_idx * 7
    if end_track_idx == 0:
        end_track_idx = len(all_tracks) - 1
    tracks_within_interval = []
    time_boundaries = TimePeriod.from_start_and_end_ms(
        start_ms=all_tracks[start_track_idx].time_period().start_ms,
        end_ms=all_tracks[end_track_idx].time_period().end_ms,
        )
    interval = time_search_interval_cls(time_boundaries)
    for track in all_tracks:
        if interval.contains(track):
            tracks_within_interval.append(track)
    fetched_tracks_within_interval = api.list_analytics_objects_tracks(
        params={'startTime': time_boundaries.start_ms, 'endTime': time_boundaries.end_ms},
        )
    return _prepare_search_result(tracks_within_interval, fetched_tracks_within_interval)


def _type_search_errors(api, all_tracks):
    start_time_ms = all_tracks[0].time_period().start_ms
    end_time_ms = all_tracks[-1].time_period().end_ms
    for track in all_tracks:
        type_id = track.type_id()
        if type_id != '':
            break
    else:
        raise RuntimeError(
            "No track with non-empty objectTypeId was found: no object type to search for")
    same_type_tracks = [track for track in all_tracks if track.type_id() == type_id]
    fetched_same_type_tracks = api.list_analytics_objects_tracks(
        params={
            'startTime': str(start_time_ms),
            'endTime': str(end_time_ms),
            'objectTypeId': type_id,
            })
    return _prepare_search_result(same_type_tracks, fetched_same_type_tracks)


def _choose_any_attribute(tracks):
    for track in tracks:
        for attr in track.attributes():
            return attr
    return None


def _text_attribute_search_errors(api, all_tracks):
    # Choosing some attribute for attribute search filter
    any_existing_attribute = _choose_any_attribute(all_tracks)
    if any_existing_attribute is None:
        return ["No track with non-empty attributes found"]
    tracks_with_attribute = [
        track for track in all_tracks if any_existing_attribute in track.attributes()]
    attribute_search_string = (
        f"{any_existing_attribute['name']}: {any_existing_attribute['value']}".lower())
    start_time_ms = all_tracks[0].time_period().start_ms
    end_time_ms = all_tracks[-1].time_period().end_ms
    fetched_tracks_with_attribute = api.list_analytics_objects_tracks(
        params={
            'startTime': str(start_time_ms),
            'endTime': str(end_time_ms),
            'freeText': attribute_search_string,
            })
    return _prepare_search_result(tracks_with_attribute, fetched_tracks_with_attribute)


def _rectangle_area_search_errors(api, tracks):
    # Intersection between a search area and a bounding box is defined within a 44x32 grid
    # (same as motion grid). 2 rectangles are considered intersecting if they share at least
    # one grid element. Test adds the size of one grid element to the sides of one rectangle
    # and checks if this extended rectangle intersects with another one.
    search_area = Rectangle(x1=0.6, y1=0.1, x2=0.9, y2=0.5)
    expected_tracks_in_area = []
    for track in tracks:
        for bounding_box in track.position_sequence():
            if search_area.overlaps(
                    bounding_box, x_accuracy=1. / 44, y_accuracy=1. / 32):
                expected_tracks_in_area.append(track)
                break
    start_time_ms = tracks[0].time_period().start_ms
    end_time_ms = tracks[-1].time_period().end_ms
    fetched_tracks_in_area = api.list_analytics_objects_tracks(
        params={
            'startTime': str(start_time_ms),
            'endTime': str(end_time_ms),
            **search_area.coordinates_dict,
            })
    return _prepare_search_result(expected_tracks_in_area, fetched_tracks_in_area)


def _test_object_search(
        distrib_url: str,
        vm_type: str,
        api_version: str,
        exit_stack: ExitStack,
        with_plugins_from_release: Optional[str] = None,
        ):
    stand = prepare_one_mediaserver_stand(
        distrib_url, vm_type, api_version, exit_stack, with_plugins_from_release)
    mediaserver = stand.mediaserver()
    recording_camera_id = exit_stack.enter_context(recording_camera(mediaserver)).id
    tracks = set_object_streamer_tracks(mediaserver, recording_camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    all_tracks = record_analytics_tracks(
        api=mediaserver.api,
        required_track_count=len(tracks),
        timeout_sec=90,
        with_positions=True,
        )
    all_tracks_log = [str(track.pretty_formatted()) for track in all_tracks]
    logging.info("Selected tracks:\n%s", '\n'.join(all_tracks_log))
    if mediaserver.newer_than('vms_6.0'):
        time_search_interval_cls = _TrackStartEndTimeSearchInterval
    elif mediaserver.newer_than('vms_5.1'):
        time_search_interval_cls = _TrackStartTimeSearchInterval
    else:
        time_search_interval_cls = _OldTimeSearchInterval
    time_interval_errors = _time_interval_search_errors(mediaserver.api, all_tracks, time_search_interval_cls)
    if time_interval_errors:
        raise Failure(f"Errors in time interval search: {time_interval_errors}")
    type_errors = _type_search_errors(mediaserver.api, all_tracks)
    if type_errors:
        raise Failure(f"Errors in type search: {type_errors}")
    text_attribute_errors = _text_attribute_search_errors(mediaserver.api, all_tracks)
    if text_attribute_errors:
        raise Failure(f"Errors in text attribute search: {text_attribute_errors}")
    area_errors = _rectangle_area_search_errors(mediaserver.api, all_tracks)
    if area_errors:
        raise Failure(f"Errors in area search: {area_errors}")
