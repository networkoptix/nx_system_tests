# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import struct
import time

from doubles.software_cameras._jpeg import JpegImage
from doubles.software_cameras._jpeg import get_frame
from doubles.software_cameras._jpeg import prepare_frames

mjpeg_fps = 30


class JPEGSequence:

    fps = mjpeg_fps

    def __init__(self, frame_size=(640, 320)):
        self.frame_size = frame_size
        self._stream_started_at = time.monotonic()
        prepare_frames(frame_size, mjpeg_fps)
        self._motion_emulation = True
        frame_text = '0'
        self.current_frame = get_frame(frame_size, frame_text)

    def _get_current_frame(self):
        if self._motion_emulation is True:
            seconds_passed = time.monotonic() - self._stream_started_at
            current_timestamp = (seconds_passed * self.fps) % self.fps
            frame_text = str(int(current_timestamp))
            self.current_frame = get_frame(self.frame_size, frame_text)
        return self.current_frame

    def get_frame(self):
        return self._get_current_frame()

    def start_motion(self):
        self._motion_emulation = True

    def stop_motion(self):
        self._motion_emulation = False


class MotionJpegStream(JPEGSequence):

    payload_type = 26
    rtpmap = b'26 JPEG/90000'

    def get_frame(self):
        return self._encode_frame(self._get_current_frame())

    def _make_quantization_table_header(self, quantization_tables: bytes):
        # See https://tools.ietf.org/html/rfc2435#section-3.1.8
        mbz = 0  # Reserved for future use and must be zero
        precision = 0
        return struct.pack(
            '>BBH%ds' % len(quantization_tables),
            mbz,
            precision,
            len(quantization_tables),
            quantization_tables)

    def _make_header(self, quantization_tables: bytes):
        # See https://tools.ietf.org/html/rfc2435#section-3.1
        type_specific = 0  # Zero if type is in range [0-127]
        frame_offset = 0  # Always send the whole frame
        # The type_ value can be calculated from JPEG header, but in case of making image using
        # PIL library, it's always 1. Since we don't have plans to use another images,
        # the value can be hard-coded.
        type_ = 1
        quantization = 255  # Q-table is present after the main JPEG header
        result = struct.pack(
            '>B3sBBBB',  # noqa SpellCheckingInspection
            type_specific,
            frame_offset.to_bytes(3, 'big'),
            type_,
            quantization,
            self.frame_size[0] // 8,
            self.frame_size[1] // 8)
        return result + self._make_quantization_table_header(quantization_tables)

    def _encode_frame(self, frame: JpegImage) -> bytes:
        codec_header = self._make_header(frame.quantization_tables)
        return codec_header + frame.scan
