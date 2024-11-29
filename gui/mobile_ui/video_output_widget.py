# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from gui.desktop_ui.media_capturing import VideoCapture
from gui.desktop_ui.widget import Widget


class VideoOutputWidget:

    def __init__(self, widget: Widget):
        self._widget = widget

    def video(self, duration: float = 3) -> VideoCapture:
        return self._widget.video(duration)

    def bounds(self):
        return self._widget.bounds()
