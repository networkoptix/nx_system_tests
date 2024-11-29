# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Sequence

import cv2
import numpy as np

from browser.color import RGBColor


class ImageCapture:

    def __init__(self, image_ndarray: np.ndarray):
        self._image = image_ndarray

    @classmethod
    def from_bytes(cls, image_bytes: bytes) -> 'ImageCapture':
        image_np_array = np.frombuffer(image_bytes, np.uint8)
        image_ndarray = cv2.imdecode(image_np_array, cv2.IMREAD_COLOR)
        return ImageCapture(image_ndarray)

    def get_height(self):
        return self._image.shape[0]

    def get_width(self):
        return self._image.shape[1]

    def crop(self, left: int, width: int, top: int, height: int) -> 'ImageCapture':
        return self.__class__(self._image[top:height, left:width])

    def get_row_colors(self, row_n: int = 0) -> Sequence['RGBColor']:
        colors = []
        row = self._image[row_n]
        for blue, green, red in row:
            colors.append(RGBColor(red, green, blue))
        return colors
