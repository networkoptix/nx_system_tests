# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from doubles.software_cameras._camera_server import CameraServer
from doubles.software_cameras._jpeg import FrameSize
from doubles.software_cameras._jpeg import JpegImage
from doubles.software_cameras._jpeg import data_is_jpeg_image
from doubles.software_cameras._motion_jpeg import JPEGSequence
from doubles.software_cameras._motion_jpeg import MotionJpegStream
from doubles.software_cameras._motion_jpeg import mjpeg_fps
from doubles.software_cameras._multi_part_jpeg import MultiPartJpegCameraServer
from doubles.software_cameras._rtsp import H264RtspCameraServer
from doubles.software_cameras._rtsp import MjpegRtspCameraServer

# Flake gives F401 (unused import) in case if there's no __all__ here
__all__ = [
    'CameraServer',
    'FrameSize',
    'H264RtspCameraServer',
    'JPEGSequence',
    'JpegImage',
    'MjpegRtspCameraServer',
    'MotionJpegStream',
    'MultiPartJpegCameraServer',
    'data_is_jpeg_image',
    'mjpeg_fps',
    ]
