# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Sequence
from typing import Tuple

from doubles.software_cameras import JpegImage

_logger = logging.getLogger(__name__)


def match_frames(
        sent_frames: Sequence[JpegImage],
        received_frames: Sequence[JpegImage]) -> Tuple[Sequence[int], Sequence[int]]:
    """Match frames, assuming that relative order is preserved."""
    sent_i, received_i = 0, 0
    skipped = []
    while sent_i < len(sent_frames) and received_i < len(received_frames):
        if sent_frames[sent_i] == received_frames[received_i]:
            received_i += 1
        else:
            skipped.append(sent_i)
        sent_i += 1
    skipped.extend(range(sent_i, len(sent_frames)))
    mismatched = range(received_i, len(received_frames))
    _logger.info(
        "Frames match: sent %d, received %d, mismatched %r, skipped %r",
        len(sent_frames), len(received_frames), mismatched, skipped)
    return skipped, mismatched
