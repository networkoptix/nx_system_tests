# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path
from typing import NamedTuple

_logger = logging.getLogger(__name__)


class _NalUnitType:
    non_idr_slice = 1
    idr_slice = 5
    sps = 7
    fu_a = 28


class _NalUnit(NamedTuple):
    raw: bytes
    nri: int
    type: int
    is_fragment: bool = False
    is_first_fragment: bool = False
    is_service_data: bool = False
    requires_timestamp_update: bool = False
    requires_rtp_marker: bool = False


def _find_delimiter(data: bytes):
    nal_unit_delimiter = b'\x00\x00\x01'
    delimiter_len = len(nal_unit_delimiter)
    delimiter_at = data.find(nal_unit_delimiter)
    if delimiter_at == -1:
        return None, None
    if data[delimiter_at - 1] == 0:  # NAL delimiter can be '00 00 00 01'
        delimiter_at -= 1
        delimiter_len += 1
    return delimiter_at, delimiter_len


def _make_nal_unit(data):
    type_ = (data[0] & 0b00011111)
    return _NalUnit(
        raw=data,
        nri=((data[0] & 0b01100000) >> 5),
        type=type_,
        requires_timestamp_update=type_ in [_NalUnitType.non_idr_slice, _NalUnitType.idr_slice],
        requires_rtp_marker=type_ in [_NalUnitType.non_idr_slice, _NalUnitType.idr_slice],
        is_service_data=type_ not in [_NalUnitType.non_idr_slice, _NalUnitType.idr_slice],
        )


def _make_fragmentation_unit(nal_unit: _NalUnit, size_bytes, offset):
    start_bit = 1 if offset == 0 else 0
    end_bit = 1 if offset + size_bytes > len(nal_unit.raw) else 0
    fu_indicator = (nal_unit.nri << 5) + _NalUnitType.fu_a
    fu_header = (start_bit << 7) + (end_bit << 6) + nal_unit.type
    fragment = nal_unit.raw[offset + 1:offset + size_bytes - 1]
    return _NalUnit(
        raw=bytes([fu_indicator, fu_header]) + fragment,
        type=_NalUnitType.fu_a,
        nri=nal_unit.nri,
        is_fragment=True,
        is_first_fragment=bool(start_bit),
        requires_timestamp_update=bool(start_bit),
        requires_rtp_marker=bool(end_bit),
        )


def _fragment_nal_unit(nal_unit: _NalUnit, size_bytes):
    fu_list = []
    offset = 0
    while offset < len(nal_unit.raw):
        fu_list.append(_make_fragmentation_unit(nal_unit, size_bytes, offset))
        offset += size_bytes - 2
    return fu_list


class H264Stream:

    payload_type = 96
    rtpmap = b'96 H264/90000'

    def __init__(self, file_path: Path, fps: int):
        self._file_path = file_path
        self._file = open(self._file_path, 'rb')
        if self._file.read(4) != b'\x00\x00\x00\x01':
            raise RuntimeError("H264 coded video file must start with '00 00 00 01'")
        self._nal_units = self._get_nal_units()
        self.fps = fps

    def close(self):
        self._file.close()

    def _get_unfragmented_nal_units(self):
        to_read_bytes = 5000
        buffer = self._file.read(to_read_bytes)
        while True:
            [delimiter_at, delimiter_len] = _find_delimiter(buffer)
            if delimiter_at is not None:
                nal_unit = _make_nal_unit(buffer[:delimiter_at])
                buffer = buffer[delimiter_at + delimiter_len:]
                yield nal_unit
                continue
            bytes_read = self._file.read(to_read_bytes)
            if not bytes_read:
                if buffer:
                    nal_unit = _make_nal_unit(buffer[:delimiter_at])
                    buffer = b''
                    yield nal_unit
                else:
                    return None
            buffer += bytes_read

    def _get_nal_units(self):
        max_bytes = 10000  # Higher frame size for fewer fragmentation and better performance
        fu_list = []
        unfragmented_nal_units = self._get_unfragmented_nal_units()
        while True:
            try:
                yield fu_list.pop(0)
            except IndexError:
                try:
                    unfragmented_nal_unit = next(unfragmented_nal_units)
                except StopIteration:
                    return None
                if len(unfragmented_nal_unit.raw) > max_bytes:
                    fu_list = _fragment_nal_unit(unfragmented_nal_unit, max_bytes)
                    yield fu_list.pop(0)
                else:
                    yield unfragmented_nal_unit

    def get_next_frame(self):
        try:
            nal_unit = next(self._nal_units)
        except StopIteration:
            self._file.seek(4)  # Skip \x00\x00\x00\x01
            self._nal_units = self._get_nal_units()
            nal_unit = next(self._nal_units)
        return nal_unit
