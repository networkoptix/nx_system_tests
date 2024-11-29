# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import io
import logging
import struct
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from typing import NamedTuple
from typing import Tuple

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

_logger = logging.getLogger(__name__)

# PIL/Pillow produces several DEBUG messages per frame but they're of no use.
# TODO: FT-1578: Revert to INFO when investigation completes.
# logging.getLogger('PIL.PngImagePlugin').setLevel(logging.INFO)


# This module contains table-specification data from RFC 2435 (RTP Payload Format
# for JPEG-compressed Video). This data is used to compose DHT headers for JPEG images.
# RFC 2435: https://tools.ietf.org/html/rfc2435 (Appendix B)
# Variable names are copied from RFC.
lum_dc_codelens = (0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0)
lum_dc_symbols = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
lum_ac_codelens = (0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 125)
lum_ac_symbols = (
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12,
    0x21, 0x31, 0x41, 0x06, 0x13, 0x51, 0x61, 0x07,
    0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xa1, 0x08,
    0x23, 0x42, 0xb1, 0xc1, 0x15, 0x52, 0xd1, 0xf0,
    0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0a, 0x16,
    0x17, 0x18, 0x19, 0x1a, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2a, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39,
    0x3a, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49,
    0x4a, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5a, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69,
    0x6a, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79,
    0x7a, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8a, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98,
    0x99, 0x9a, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7,
    0xa8, 0xa9, 0xaa, 0xb2, 0xb3, 0xb4, 0xb5, 0xb6,
    0xb7, 0xb8, 0xb9, 0xba, 0xc2, 0xc3, 0xc4, 0xc5,
    0xc6, 0xc7, 0xc8, 0xc9, 0xca, 0xd2, 0xd3, 0xd4,
    0xd5, 0xd6, 0xd7, 0xd8, 0xd9, 0xda, 0xe1, 0xe2,
    0xe3, 0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9, 0xea,
    0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8,
    0xf9, 0xfa,
    )
chm_dc_codelens = (0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0)
chm_dc_symbols = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
chm_ac_codelens = (0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 119)
chm_ac_symbols = (
    0x00, 0x01, 0x02, 0x03, 0x11, 0x04, 0x05, 0x21,
    0x31, 0x06, 0x12, 0x41, 0x51, 0x07, 0x61, 0x71,
    0x13, 0x22, 0x32, 0x81, 0x08, 0x14, 0x42, 0x91,
    0xa1, 0xb1, 0xc1, 0x09, 0x23, 0x33, 0x52, 0xf0,
    0x15, 0x62, 0x72, 0xd1, 0x0a, 0x16, 0x24, 0x34,
    0xe1, 0x25, 0xf1, 0x17, 0x18, 0x19, 0x1a, 0x26,
    0x27, 0x28, 0x29, 0x2a, 0x35, 0x36, 0x37, 0x38,
    0x39, 0x3a, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48,
    0x49, 0x4a, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58,
    0x59, 0x5a, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68,
    0x69, 0x6a, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78,
    0x79, 0x7a, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87,
    0x88, 0x89, 0x8a, 0x92, 0x93, 0x94, 0x95, 0x96,
    0x97, 0x98, 0x99, 0x9a, 0xa2, 0xa3, 0xa4, 0xa5,
    0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xb2, 0xb3, 0xb4,
    0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xc2, 0xc3,
    0xc4, 0xc5, 0xc6, 0xc7, 0xc8, 0xc9, 0xca, 0xd2,
    0xd3, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xd9, 0xda,
    0xe2, 0xe3, 0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9,
    0xea, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8,
    0xf9, 0xfa,
    )


class _CorruptedFile(Exception):
    pass


class FrameSize(NamedTuple):
    width: int
    height: int


class JpegImage:

    _start_of_image = b'\xff\xd8'
    _app0 = b'\xff\xe0'
    _define_quantization_table = b'\xff\xdb'
    _start_of_frame = b'\xff\xc0'
    _define_huffman_table = b'\xff\xc4'
    _start_of_scan = b'\xff\xda'
    _end_of_image = b'\xff\xd9'

    def __init__(self, raw: bytes):
        # See: https://www.ccoderun.ca/programming/2017-01-31_jpeg/
        buffer = io.BytesIO(raw)
        self.raw: bytes = raw
        if buffer.read(2) != self._start_of_image:
            raise _CorruptedFile("This is not a JPEG image")
        self._fields = []
        frame_size = None
        while True:
            marker = buffer.read(2)
            if not marker.startswith(b'\xff'):
                raise _CorruptedFile(
                    f"Corrupted image file; marker must start with '\\xff'; marker: {marker}")
            [length] = struct.unpack('>H', buffer.read(2))
            value = buffer.read(length - 2)
            if marker == self._app0:
                # APP0 header can be absent if the image was extracted from the RTSP stream.
                # It doesn't affect the ability to view this image, so it can be omitted.
                continue
            if marker == self._start_of_frame:
                height, width = struct.unpack_from('>HH', value, offset=1)
                frame_size = FrameSize(width, height)
                continue
            self._fields.append((marker, value))
            if marker == self._start_of_scan:
                scan_with_end_of_image = buffer.read()
                self.scan = scan_with_end_of_image[:-2]
                end_of_image = scan_with_end_of_image[-2:]
                if end_of_image != self._end_of_image:
                    raise _CorruptedFile(
                        f"Corrupted image file; image must end with {self._end_of_image!r}")
                break
        if frame_size is None:
            raise RuntimeError("Can't find JPEG Start of Frame tag")
        self.frame_size = frame_size
        self.quantization_tables = b''
        for marker, value in self._fields:
            if marker == self._define_quantization_table:
                self.quantization_tables += value[1:]

    def __len__(self):
        return len(self.raw)

    def __eq__(self, other):
        if not isinstance(other, JpegImage):
            return NotImplemented
        return self._fields == other._fields and self.scan == other.scan

    def __repr__(self):
        return f"<{self.__class__.__name__}, size: {len(self)} bytes>"

    @classmethod
    def _make_sof_header(cls, height: int, width: int):
        length_field = struct.pack('>H', 17)
        precision = b'\x08'  # Can be 12 or 16 as well, but 8 is the most common
        sof_header = cls._start_of_frame + length_field
        sof_header += precision + struct.pack('>HH', height, width)
        number_of_components = b'\x03'  # YCbCr
        sof_header += number_of_components
        [y_component_id, cb_component_id, cr_component_id] = b'\x01', b'\x02', b'\x03'
        # Component field values depend on quantization type. These values are hard-coded
        # because only one type is supported and they are too low-level.
        y_component = y_component_id + b'\x22\x00'
        cb_component = cb_component_id + b'\x11\x01'
        cr_component = cr_component_id + b'\x11\x01'
        sof_header += y_component + cb_component + cr_component
        return sof_header

    @classmethod
    def _make_quantization_table(cls, table_data, destination):
        header_length = 3
        length_field = struct.pack('>H', len(table_data) + header_length)
        return cls._define_quantization_table + length_field + destination + table_data

    @classmethod
    def _make_huffman_table(cls, codelens, symbols, class_and_destination):
        header_length = 3
        table_data = bytes(codelens) + bytes(symbols)
        length_field = struct.pack('>H', len(table_data) + header_length)
        return cls._define_huffman_table + length_field + class_and_destination + table_data

    @classmethod
    def _make_sos_header(cls):
        length_field = struct.pack('>H', 12)
        number_of_components = b'\x03'  # YCbCr
        sos_header = cls._start_of_scan + length_field + number_of_components
        [y_component_id, cb_component_id, cr_component_id] = b'\x01', b'\x02', b'\x03'
        # Component field values depend on quantization type. These values are hard-coded
        # because only one type is supported and they are too low-level. The same with
        # the spectral selection / approximate bit positions values.
        y_component = y_component_id + b'\x00'
        cb_component = cb_component_id + b'\x11'
        cr_component = cr_component_id + b'\x11'
        sos_header += y_component + cb_component + cr_component
        spectral_selection_start = b'\x00'
        spectral_selection_end = b'\x3f'
        approximate_bit_positions = b'\x00'
        sos_header += spectral_selection_start + spectral_selection_end + approximate_bit_positions
        return sos_header

    @classmethod
    def from_data(cls, quantization_tables, width, height, scan):
        raw = cls._start_of_image
        # The only type of quantization tables data supported is: two 64-byte
        # quantization tables, one for the luminance component and one for the
        # chrominance component.
        if len(quantization_tables) != 128:
            raise NotImplementedError("Only quantization tables length of 128 is supported")
        quantization_table_length = 64
        luminance_table = quantization_tables[:quantization_table_length]
        chrominance_table = quantization_tables[quantization_table_length:]
        raw += cls._make_quantization_table(luminance_table, b'\x00')
        raw += cls._make_quantization_table(chrominance_table, b'\x01')
        raw += cls._make_sof_header(height, width)
        raw += cls._make_huffman_table(lum_dc_codelens, lum_dc_symbols, b'\x00')
        raw += cls._make_huffman_table(lum_ac_codelens, lum_ac_symbols, b'\x10')
        raw += cls._make_huffman_table(chm_dc_codelens, chm_dc_symbols, b'\x01')
        raw += cls._make_huffman_table(chm_ac_codelens, chm_ac_symbols, b'\x11')
        raw += cls._make_sos_header()
        raw += scan + cls._end_of_image
        return cls(raw)


def data_is_jpeg_image(data):
    try:
        JpegImage(data)
    except _CorruptedFile:
        return False
    else:
        return True


_frame_cache = defaultdict(dict)


def _make_frame(frame_size: Tuple[int, int], text: str) -> JpegImage:
    [width, height] = frame_size
    _logger.debug("Make JPEG: resolution=%dx%d; text=%s", width, height, text)
    scale = 10
    buf = io.BytesIO()
    image = Image.new('RGB', (width // scale, height // scale), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    [_, _, text_width, text_height] = draw.textbbox((0, 0), text, font=ImageFont.load_default())
    white = (255, 255, 255)
    offset = ((width // scale - text_width) // 2, (height // scale - text_height) // 2)
    draw.text(offset, text, fill=white)
    image = image.resize((width, height))
    image.save(buf, format='jpeg')
    frame = JpegImage(buf.getvalue())
    return frame


def prepare_frames(frame_size: Tuple[int, int], frames_count):
    with ThreadPoolExecutor(max_workers=frames_count) as executor:
        frame_fut_to_text = {
            executor.submit(_make_frame, frame_size, str(text)): str(text)
            for text
            in range(frames_count)
            }
        for fut in as_completed(frame_fut_to_text):
            text = frame_fut_to_text[fut]
            _frame_cache[frame_size][text] = fut.result()


def get_frame(frame_size, text):
    return _frame_cache[frame_size][text]


if __name__ == '__main__':
    image = _make_frame((640, 420), 'test')
