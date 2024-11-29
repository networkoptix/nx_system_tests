# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import dataclasses
import logging
import math
from collections import Counter
from pathlib import Path
from typing import List
from typing import Sequence
from typing import Tuple

import cv2
import numpy as np

from gui.desktop_ui.screen import ScreenRectangle

_logger = logging.getLogger(__name__)


class VideoCapture:
    """Capture video frame-by-frame making screenshots."""

    def __init__(self, frames: Sequence['ImageCapture']):
        self._frames = frames

    def play(self):
        # show video in a window for debug purposes
        for frame in self._frames:
            cv2.imshow('diff_frame', frame)

    def get_grayscale(self):
        new_frames = []
        for frame in self._frames:
            new_frames.append(frame.get_grayscale())
        return VideoCapture(new_frames)

    def has_different_frames(self):
        """Compare serial frames.

        If captured video has different frames - then it was playing at the
        time of capture. The opposite isn't true in case of stationary
        videos if they were generated, not recorded.
        """
        prev_frame = None
        for frame in self.get_grayscale()._frames:
            if prev_frame is not None:
                are_frames_same = frame.is_similar_to(
                    prev_frame,
                    correlation=0.98,
                    )
                if not are_frames_same:
                    return True
            prev_frame = frame
        return False

    def crop_percentage(self, crop_area: 'ImagePiecePercentage') -> 'VideoCapture':
        new_frames = []
        for frame in self._frames:
            new_frame = frame.crop_percentage(crop_area)
            new_frames.append(new_frame)
        return VideoCapture(new_frames)

    def has_motion_mask(self):
        # video has motion mask if any of its pixels is of red "pixel mask" color
        # will work correctly only if video itself is grayscale and doesn't interfere with the mask
        RED_MASK_COLOR = HsvColorInterval((0, 100, 20), (15, 255, 255))
        for frame in self._frames:
            if frame.has_color_hsv(RED_MASK_COLOR):
                return True
        return False


class ImageCapture:

    def __init__(self, image: np.ndarray):
        # This is a cv2 image - np.ndarray in python.
        self._image = image

    def get_aspect_ratio(self):
        return self.get_width() / self.get_height()

    def is_grayscale(self):
        # if image is grayscale it has only 2 dimensions
        return self._image.ndim == 2

    def get_height(self):
        return self._image.shape[0]

    def get_width(self):
        return self._image.shape[1]

    def most_common_colors(self, colors_count=5):
        counter = Counter()
        for row in self._image:
            for b, g, r in row:
                counter[f'#{r:02x}{g:02x}{b:02x}'] += 1
        return counter.most_common(colors_count)

    def get_grayscale(self):
        r = ImageCapture(
            self._image
            if self.is_grayscale()
            else cv2.cvtColor(self._image, cv2.COLOR_BGRA2GRAY),
            )
        return r

    def save_to_disk(self, path: Path):
        if path.exists():
            path.unlink()
        cv2.imwrite(str(path), self._image)

    def resize(self, width, height, interpolation=cv2.INTER_LINEAR) -> 'ImageCapture':
        image = cv2.resize(
            self._image,
            (int(width), int(height)),
            interpolation=interpolation,
            )
        r = ImageCapture(image)
        return r

    def scale(self, scale: float, interpolation=cv2.INTER_LINEAR) -> 'ImageCapture':
        if np.isclose(scale, 1.0):
            return self
        return self.resize(self.get_width() * scale, self.get_height() * scale, interpolation)

    def transpose(self, axes: Sequence[int]):
        _image = self._image.transpose(axes)
        return ImageCapture(_image)

    def normalize_image(self, mean: Sequence[float], std: Sequence[float], scale: float):
        scale = np.float32(scale)
        mean = np.array(mean).reshape(1, 1, 3).astype('float32')
        std = np.array(std).reshape(1, 1, 3).astype('float32')
        _image = (self._image.astype('float32') * scale - mean) / std
        return ImageCapture(_image)

    def crop_border(self, pixels):
        return self.crop(pixels, self.get_width() - pixels, pixels, self.get_height() - pixels)

    def crop(self, x: int, x1, y: int, y1: int) -> 'ImageCapture':
        r = ImageCapture(self._image[y:y1, x:x1])
        return r

    def make_rectangle(self, crop_area: 'ImagePiecePercentage') -> 'ScreenRectangle':
        x_min = max(0, int(self.get_width() * crop_area.offset_x))
        y_min = max(0, int(self.get_height() * crop_area.offset_y))
        x_max = min(self.get_width(), x_min + int(self.get_width() * crop_area.width))
        y_max = min(self.get_height(), y_min + int(self.get_height() * crop_area.height))
        return ScreenRectangle(x_min, y_min, x_max - x_min, y_max - y_min)

    def crop_percentage(self, crop_area: 'ImagePiecePercentage') -> 'ImageCapture':
        # crop based on percent values
        rectangle = self.make_rectangle(crop_area)
        return self.crop(
            rectangle.top_left().x, rectangle.bottom_right().x,
            rectangle.top_left().y, rectangle.bottom_right().y,
            )

    def is_similar_to(
            self,
            expected: 'ImageCapture',
            correlation=0.85,
            crop_border_pixels=None,
            check_aspect_ratio=True,
            aspect_ratio_error=0.02,
            colors=False,
            ):
        if check_aspect_ratio:
            delta = abs(self.get_aspect_ratio() - expected.get_aspect_ratio())
            if not delta < aspect_ratio_error:
                _logger.debug(
                    f'Aspect ratio of current behavior: {self.get_aspect_ratio()}\n'
                    + f'Aspect ratio of expected screenshot: {expected.get_aspect_ratio()}\n'
                    + f'Limit of error: {aspect_ratio_error}',
                    )
                raise RuntimeError("Aspect ratio is wrong.")

        expected = expected.resize(self.get_width(), self.get_height())
        current = ImageCapture(self._image)

        if not colors:
            expected = expected.get_grayscale()
            current = self.get_grayscale()

        # Sometimes images differ significantly on border, especially when one of the
        # images was cropped from a bigger image.
        # To improve correlation we can crop 1-3 pixels from border.
        if crop_border_pixels is not None:
            expected = expected.crop_border(crop_border_pixels)
            current = current.crop_border(crop_border_pixels)

        res = cv2.matchTemplate(expected._image, current._image, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        result = max_val > correlation
        if not result:
            _logger.debug('Pictures correlation: %s', max_val)
        return result

    def get_row_colors(self, row_n: int = 0) -> Sequence['RGBColor']:
        colors = []
        row = self._image[row_n]
        for blue, green, red in row:
            colors.append(RGBColor(red, green, blue))
        return colors

    def show(self):
        cv2.imshow('temp', self._image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def rotate(self, angle):
        (cX, cY) = (self.get_width() // 2, self.get_height() // 2)

        # grab the rotation matrix (applying the negative of the
        # angle to rotate clockwise), then grab the sine and cosine
        # (i.e., the rotation components of the matrix)
        matrix = cv2.getRotationMatrix2D((cX, cY), -angle, 1.0)
        cos = np.abs(matrix[0, 0])
        sin = np.abs(matrix[0, 1])

        # compute the new bounding dimensions of the image
        new_weight = int((self.get_height() * sin) + (self.get_width() * cos))
        new_height = int((self.get_height() * cos) + (self.get_width() * sin))

        # adjust the rotation matrix to take into account translation
        matrix[0, 2] += (new_weight / 2) - cX
        matrix[1, 2] += (new_height / 2) - cY

        # perform the actual rotation and return the image
        r = ImageCapture(
            cv2.warpAffine(self._image, matrix, (new_weight, new_height)),
            )
        return r

    def has_color_hsv(self, color: 'HsvColorInterval'):
        # returns true if there is color in image that is in hsv_range
        mask = cv2.inRange(
            cv2.cvtColor(self._image, cv2.COLOR_BGR2HSV),
            color.hsv_min,
            color.hsv_max,
            )
        return np.max(mask) > 0

    def has_color_rgb(self, color: 'RGBColor'):
        for d1 in self._image:
            for blue, green, red in d1:
                if RGBColor(red, green, blue) == color:
                    return True
        return False

    def calculate_scale(self, scale: float = 2.0) -> float:
        min_dimension = min(self.get_width(), self.get_height())
        # Resize if image is small, 50 pixels is empiric "enough".
        if min_dimension < 50:
            scale = 50 / min_dimension
        return scale

    def scale_grayscale(self, desired_scale: float = 2.0) -> (List[np.ndarray], float):
        scale = self.calculate_scale(desired_scale)
        scaled_image = self.get_grayscale().scale(
            scale,
            interpolation=cv2.INTER_CUBIC)
        return scaled_image._image, scale

    def as_numpy_array(self) -> np.ndarray:
        return self._image


class Screenshot(ImageCapture):

    def __init__(self, buffer, bounds: ScreenRectangle):
        self._buffer = buffer
        mt = np.frombuffer(buffer, np.uint8)
        img = cv2.imdecode(mt, cv2.IMREAD_COLOR)
        x1, y1 = bounds.top_left()
        x2, y2 = bounds.bottom_right()
        img = img[y1:y2, x1:x2]
        super().__init__(img)
        self._bounds: ScreenRectangle = bounds

    def region_bounds(self, x, y, width, height):
        return ScreenRectangle(
            self._bounds.top_left().right(x).x,
            self._bounds.top_left().down(y).y,
            width,
            height,
            )

    def crop(self, x: int, x1, y: int, y1: int) -> 'Screenshot':
        bounds = ScreenRectangle(
            self._bounds.x + x,
            self._bounds.y + y,
            x1 - x,
            y1 - y,
            )
        return Screenshot(self._buffer, bounds)

    def find_image_occurrences(
            self, other: 'ImageCapture',
            min_scale=0.2, max_scale=1.0,
            scale_steps=40, threshold=0.9,
            ) -> List[ScreenRectangle]:
        # try to find image in self
        # multiple occurrences of different size are supported
        # for this we iterate over possible scales and try to match each
        # with more steps process is slower but more accurate
        results = []
        for scale in np.linspace(min_scale, max_scale, scale_steps)[::-1]:
            scaled_other = other.get_grayscale().scale(scale)
            scaled_other_is_smaller = (
                    scaled_other.get_width() <= self.get_width()
                    and scaled_other.get_height() <= self.get_height())
            if scaled_other_is_smaller:
                match = cv2.matchTemplate(
                    self.get_grayscale()._image,
                    scaled_other._image,
                    cv2.TM_CCOEFF_NORMED,
                    )
                _, max_val, _, _ = cv2.minMaxLoc(match)
                if max_val > threshold:
                    # points found is a list of coordinates where rectangles with the image start
                    # due to threshold there can be multiple findings of near-same coords
                    # we filter out intersecting ones
                    points_found = np.where(match >= threshold)
                    rectangles = []
                    for x, y in zip(*points_found[::-1]):
                        rect = ScreenRectangle(
                            self._bounds.x + int(x),
                            self._bounds.y + int(y),
                            scaled_other.get_width(),
                            scaled_other.get_height())
                        rectangles.append(rect)

                    for new_rect in rectangles:
                        for rect in results:
                            if rect.contains_point(new_rect.top_left()):
                                break
                        else:
                            results.append(new_rect)
        _logger.debug('Found %s image occurrences total', len(results))
        return results


class SavedImage(ImageCapture):

    def __init__(self, path: Path):
        raw = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        super().__init__(raw)


@dataclasses.dataclass
class HsvColorInterval:
    """Defined as interval, where we expect target color to be.

    Primarily useful when color is transparent and has background.
    So we cannot use fixed RGB value.
    Example is motion detection squares on scene items "#c80000.setAlpha(51)" => transparent
    """

    hsv_min: Tuple[int, int, int]
    hsv_max: Tuple[int, int, int]


class CIELABColor:

    def __init__(self, l_star: float, a_star: float, b_star: float):
        if not 0.0 <= l_star <= 100.0:
            raise ValueError(
                "Luminance value must be between 0.0 and 100.0 borders included. "
                f"Got: {l_star}")
        elif not -128.0 <= a_star <= 127:
            raise ValueError(
                "Red-Green axis value should be between -128.0 and 127.0 borders included. "
                f"Got: {a_star}")
        elif not -128.0 <= b_star <= 127:
            raise ValueError(
                "Blue-Yellow axis value should be between -128.0 and 127.0 borders included. "
                f"Got: {b_star}")
        self._luminance = l_star
        self._red_green = a_star
        self._blue_yellow = b_star

    def _calculate_delta(self, other: 'CIELABColor') -> float:
        # See: https://www.ulprospector.com/knowledge/10780/pc-the-cielab-lab-system-the-method-to-quantify-colors-of-coatings/
        euclidean_distance = math.dist(
            (self._luminance, self._red_green, self._blue_yellow),
            (other._luminance, other._red_green, other._blue_yellow),
            )
        logging.debug("%r: CIELAB Distance with %r is %.06f", self, other, euclidean_distance)
        return euclidean_distance

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        delta = self._calculate_delta(other)
        # See: https://www.viewsonic.com/library/creative-work/what-is-delta-e-and-why-is-it-important-for-color-accuracy/
        return delta <= 2.0

    def is_shade_of(self, other: 'CIELABColor') -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        delta = self._calculate_delta(other)
        # See: https://www.viewsonic.com/library/creative-work/what-is-delta-e-and-why-is-it-important-for-color-accuracy/
        return delta <= 10.0

    def __repr__(self):
        name = self.__class__.__name__
        return f'{name}({self._luminance:.03f}, {self._red_green:.03f}, {self._blue_yellow:.03f})'


class RGBColor(CIELABColor):
    # Many values can be found here
    # nx/open/vms/client/nx_vms_client_desktop/external_resources/skin/basic_colors.json

    def __init__(self, red: int, green: int, blue: int):
        if not 0 <= red <= 255:
            raise ValueError(f"Red color value must be in range 0-255. Received: {red}")
        if not 0 <= green <= 255:
            raise ValueError(f"Green color value must be in range 0-255. Received: {green}")
        if not 0 <= blue <= 255:
            raise ValueError(f"Blue color value must be in range 0-255. Received: {blue}")
        x, y, z = _rgb_to_xyz(red, green, blue)
        luminance, red_green, blue_yellow = _xyz_to_cielab(x, y, z)
        super().__init__(luminance, red_green, blue_yellow)
        self._red = red
        self._green = green
        self._blue = blue

    def __repr__(self):
        return f'{self.__class__.__name__}({self._red:03d}, {self._green:03d}, {self._blue:03d})'


def _rgb_to_xyz(red: int, green: int, blue: int) -> Tuple[float, float, float]:
    # See: http://www.easyrgb.com/en/math.php
    # See: https://colorcalculations.wordpress.com/xyz-to-rgb/
    red = _xyz_transform_single_rgb_color(red)
    green = _xyz_transform_single_rgb_color(green)
    blue = _xyz_transform_single_rgb_color(blue)
    x = red * 0.4124 + green * 0.3576 + blue * 0.1805
    y = red * 0.2126 + green * 0.7152 + blue * 0.0722
    z = red * 0.0193 + green * 0.1192 + blue * 0.9505
    return x, y, z


def _xyz_transform_single_rgb_color(color: int) -> float:
    result = color / 255
    result = (((result + 0.055) / 1.055) ** 2.4) if (result > 0.04045) else (result / 12.92)
    result *= 100
    return result


def _xyz_to_cielab(x: float, y: float, z: float) -> Tuple[float, float, float]:
    # See: http://www.easyrgb.com/en/math.php
    # See: https://rip94550.wordpress.com/2011/07/04/color-cielab-and-tristimulus-xyz/
    x, y, z = _d65_2_deg_transform(x, y, z)
    x_transformed = _transform_xyz_axis(x)
    y_transformed = _transform_xyz_axis(y)
    z_transformed = _transform_xyz_axis(z)
    luminance = (116 * y_transformed) - 16
    red_green = 500 * (x_transformed - y_transformed)
    blue_yellow = 200 * (y_transformed - z_transformed)
    return luminance, red_green, blue_yellow


def _d65_2_deg_transform(x: float, y: float, z: float) -> Tuple[float, float, float]:
    # Daylight, sRGB, Adobe-RGB 2 degrees angle
    x_ref = x / 95.047
    y_ref = y / 100.0
    z_ref = z / 108.883
    return x_ref, y_ref, z_ref


def _transform_xyz_axis(axis: float) -> float:
    return axis ** (1 / 3) if axis > 0.008856 else (7.787 * axis) + (16 / 116)


class CSSColor(RGBColor):

    def __init__(self, value: str):
        if not value.startswith('#'):
            raise RuntimeError("Hex values for RGB colors must start with #")
        value = int(value.lstrip('#'), base=16)
        red = (value & 0xFF_00_00) >> 16
        green = (value & 0x00_FF_00) >> 8
        blue = value & 0x00_00_FF
        super().__init__(red, green, blue)
        self._value = value

    def __repr__(self):
        return f'CSSColor({self._value!r})'


def get_contours(prediction_bitmap: np.ndarray) -> List[np.ndarray]:
    contours, _ = cv2.findContours(
        (prediction_bitmap * 255).astype(np.uint8),
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE,
        )
    return contours


def get_rectangle_from_contour(contour: np.ndarray) -> ScreenRectangle:
    return ScreenRectangle(*cv2.boundingRect(contour))


@dataclasses.dataclass
class ImagePiecePercentage:
    """Piece of image that works for images of any size.

    Based on percent values. All values parts of 1.
    """

    offset_x: float
    offset_y: float
    width: float
    height: float
