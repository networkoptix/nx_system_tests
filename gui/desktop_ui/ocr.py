# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import multiprocessing
import re
import string
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache
from typing import Optional
from typing import Sequence
from typing import Tuple

import numpy as np
import onnxruntime
import pytesseract

from _internal.service_registry import models_prerequisite_store
from gui.desktop_ui.media_capturing import ImageCapture
from gui.desktop_ui.media_capturing import Screenshot
from gui.desktop_ui.media_capturing import get_contours
from gui.desktop_ui.media_capturing import get_rectangle_from_contour
from gui.desktop_ui.screen import ScreenRectangle

_logger = logging.getLogger(__name__)

_model_path = models_prerequisite_store.fetch('detection_model.onnx')
_onnx_runner = onnxruntime.InferenceSession(_model_path.as_posix())


class TextNotFound(Exception):
    pass


class WrongFormat(Exception):
    pass


class Outlier(Exception):
    pass


class _TextAreaCapture:

    def __init__(self, image: 'Screenshot'):
        self._image = image

    def detect_text_boxes(self) -> Sequence['_DetectedBox']:
        prediction_bitmap = self._get_prediction_map()
        contours = get_contours(prediction_bitmap)
        # Contours are reverse numbered,
        # So we read them backwards to keep the order of the text boxes
        detected_boxes = []
        for contour in contours[::-1]:
            try:
                rectangle = self._get_rectangle(contour)
            except Outlier:
                continue
            box = _DetectedBox(rectangle, self._image)
            detected_boxes.append(box)
        _logger.debug(f'Were detected {len(detected_boxes)!r} boxes')
        return detected_boxes

    def _get_prediction_map(self) -> np.ndarray:
        resized_image = self._get_resized_image()
        std = [0.229, 0.224, 0.225]
        mean = [0.485, 0.456, 0.406]
        scale = 1.0 / 255.0
        normalized_image = resized_image.normalize_image(mean, std, scale)
        # Transform the channels into the format expected by the neural network HWC -> CHW
        transposed_image_array = normalized_image.transpose(axes=[2, 0, 1]).as_numpy_array()
        onnx_input = {'x': np.expand_dims(transposed_image_array, axis=0)}
        [prediction_map, *_] = _onnx_runner.run(None, onnx_input)
        threshold_prediction_map = prediction_map[0, 0, :, :] > 0.05
        return threshold_prediction_map

    @lru_cache(1)
    def _get_resized_image(self) -> 'ImageCapture':
        # Current models only support images that are multiples of 32
        # Resize the image to the nearest multiple of 32
        multiplicand = 32
        scale_factor = _get_scale_factor(
            multiplicand * 20, multiplicand * 45,
            self._image.get_height(), self._image.get_width(),
            )
        resized_width = _nearest_multiplication(
            self._image.get_width(),
            scale_factor,
            multiplicand,
            )
        resized_height = _nearest_multiplication(
            self._image.get_height(),
            scale_factor,
            multiplicand,
            )
        return self._image.resize(resized_width, resized_height)

    def _get_rectangle(self, contour) -> Optional[ScreenRectangle]:
        rectangle = get_rectangle_from_contour(contour)
        if min(rectangle.width, rectangle.height) < 5:
            raise Outlier('Detected rectangle is too small')
        return rectangle.axis_scaling(
            self._image.get_width() / self._get_resized_image().get_width(),
            self._image.get_height() / self._get_resized_image().get_height(),
            self._image.get_width(),
            self._image.get_height(),
            )


class _DetectedBox:

    def __init__(self, rectangle: ScreenRectangle, image: 'Screenshot'):
        self._image = image
        self._rectangle = rectangle
        self._scale_factor = 1.0

    def get_rectangle(self) -> ScreenRectangle:
        return self._rectangle

    def get_text_lines(self):
        text_config = "--oem 3 --psm 6 -l eng"
        return self._recognize_text(text_config)

    def get_digit_lines(self):
        digits_config = f"--oem 3 --psm 6 -l eng -c tessedit_char_whitelist={string.digits}"
        return self._recognize_text(digits_config)

    def box_to_image_region(self) -> ScreenRectangle:
        return self._image.region_bounds(
            self._rectangle.x, self._rectangle.y,
            self._rectangle.width, self._rectangle.height,
            )

    def _recognize_text(self, config: str) -> str:
        bordered_rectangle = self._scale_detected_rectangle()
        cropped_image_array = self._crop_by_rectangle(bordered_rectangle)
        try:
            text = pytesseract.image_to_string(cropped_image_array, config=config)
        except ValueError as e:
            raise TextNotFound('Failed to recognize text %s', e)
        return text

    def _scale_detected_rectangle(self) -> ScreenRectangle:
        _border_factor = 2.5
        _max_font_size = 50
        _min_font_size = 5
        self._scale_factor = _get_scale_factor(
            _min_font_size,
            _max_font_size,
            self._rectangle.height,
            )
        # Expand the box using border factor
        bordered_rectangle = self._rectangle.add_borders(
            _border_factor,
            [self._image.get_width(), self._image.get_height()],
            )
        return bordered_rectangle

    def _crop_by_rectangle(self, bordered_rectangle: ScreenRectangle) -> np.ndarray:
        grayscale_image = self._image.get_grayscale()
        cropped_image = grayscale_image.crop(
            bordered_rectangle.top_left().x, bordered_rectangle.bottom_right().x,
            bordered_rectangle.top_left().y, bordered_rectangle.bottom_right().y,
            )
        cropped_image = cropped_image.scale(self._scale_factor)
        return cropped_image.as_numpy_array()


class ImageTextRecognition:

    def __init__(self, capture: 'Screenshot'):
        self._capture = capture
        self._detected_boxes = _TextAreaCapture(capture).detect_text_boxes()

    def get_raw_rectangle_by_index(self, index: int) -> ScreenRectangle:
        return self._detected_boxes[index].get_rectangle()

    def get_rectangle_by_index(self, index: int) -> ScreenRectangle:
        return self._detected_boxes[index].box_to_image_region()

    def has_paragraph(self, expected_text: str) -> bool:
        cleaned_expected_text, lines_without_punctuation = self._remove_punctuation(expected_text)
        paragraph_without_punctuation = " ".join(lines_without_punctuation)
        if cleaned_expected_text in paragraph_without_punctuation:
            return True
        _logger.info(f'Expected text {expected_text!r} not found')
        return False

    def line_index(self, expected_text: str) -> int:
        cleaned_expected_text, lines_without_punctuation = self._remove_punctuation(expected_text)
        for index, line in enumerate(lines_without_punctuation):
            if cleaned_expected_text in line:
                return index
        raise TextNotFound(f'Expected text {expected_text!r} not found')

    def line_index_by_pattern(self, pattern: re.Pattern) -> int:
        lines_without_punctuation = [
            _remove_punctuation(line) for line in self._get_recognized_lines()
            ]
        for index, text in enumerate(lines_without_punctuation):
            if pattern.match(text) is not None:
                return index
        raise TextNotFound(f'No text matching the pattern {pattern!r} was found')

    def has_line(self, expected_text: str) -> bool:
        try:
            self.line_index(expected_text)
            return True
        except TextNotFound:
            return False

    def multiple_line_indexes(self, expected_texts: Sequence[str]) -> Sequence[int]:
        indexes = []
        for expected_text in expected_texts:
            index = self.line_index(expected_text)
            indexes.append(index)
        return indexes

    def get_phrase_rectangle(self, expected_text: str) -> ScreenRectangle:
        index = self.line_index(expected_text)
        return self.get_rectangle_by_index(index)

    def datetime_index(self) -> int:
        # Datetime formats in NxClient differ in patterns and value (January vs Январь).
        # Now we do not check any other languages except for English. In the future we have
        # to change the constant to a normal method that takes locale from remote machine.
        # if ocr text parses correctly then there is a valid timestamp on video
        collect_errors = ['No texts were recognized']
        format_string = '%A %B %d %Y %I:%M:%S %p'
        for index, line in enumerate(self._get_recognized_lines()):
            line_without_punctuation = _remove_punctuation(line)
            try:
                # timestamp language/format depends on current locale
                # commas not very reliable with ocr
                datetime.strptime(line_without_punctuation, format_string)
                return index
            except ValueError as e:
                collect_errors.append(str(e))
        raise WrongFormat(' '.join(collect_errors))

    def _remove_punctuation(self, expected_text: str) -> Tuple[str, Sequence[str]]:
        cleaned_expected_text = _remove_punctuation(expected_text)
        lines_without_punctuation = [
            _remove_punctuation(line) for line in self._get_recognized_lines()
            ]
        return cleaned_expected_text, lines_without_punctuation

    @lru_cache()
    def _get_recognized_lines(self) -> Sequence[str]:
        with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count() + 4) as executor:
            results = executor.map(
                lambda box: box.get_text_lines(),
                self._detected_boxes,
                timeout=5,
                )
            texts = [*results]
        _logger.debug(f'Recognized text {texts!r}')
        return texts


class ImageDigitsRecognition:

    def __init__(self, capture: 'Screenshot'):
        self._detected_boxes: _DetectedBox = _TextAreaCapture(capture).detect_text_boxes()

    def compare_ocr_results(self, other_num_comparer: 'ImageDigitsRecognition', offset: int):
        for left_number in self._to_int():
            for right_number in other_num_comparer._to_int():
                if left_number + offset == right_number:
                    return True
        return False

    def has_in_delta_neighborhood(self, expected_number: int, delta: float):
        for number in self._to_int():
            if abs(expected_number - number) <= abs(delta):
                return True
        return False

    def _to_int(self):
        for value in self._get_recognized_lines():
            try:
                yield int(value)
            except ValueError:
                continue

    @lru_cache()
    def _get_recognized_lines(self) -> Sequence[str]:
        with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count() + 4) as executor:
            results = executor.map(
                lambda box: box.get_digit_lines(),
                self._detected_boxes,
                timeout=5,
                )
            texts = [*results]
        _logger.debug(f'Recognized text {texts!r}')
        return texts


def _remove_punctuation(text: str, exception: str = ':') -> str:
    # We replace all non-alphanumeric characters by spaces,
    # because tesseract barely deal with them,
    # but we keep exception characters for cases like datetime format when ':' sign is important
    escaped_exception = re.escape(exception)
    cleaned_text = re.sub(f'[^{escaped_exception}0-9a-zA-Z]+', ' ', text)

    return cleaned_text.strip().lower()


def _get_scale_factor(lower_limit_side, upper_limit_side, height, width=None) -> float:
    ratio = 1.0
    size_limits = [lower_limit_side, upper_limit_side]
    size_extreme_functions = [min, max]
    for size_limit, func in zip(size_limits, size_extreme_functions):
        size_extreme = height if width is None else func(height, width)
        ratio = size_limit / func(size_extreme, size_limit)
        if ratio != 1.0:
            break
    return ratio


def _nearest_multiplication(number, ratio, multiplicand):
    nearest_multiplier = round(number * ratio / multiplicand) * multiplicand
    return int(max(nearest_multiplier, multiplicand))
