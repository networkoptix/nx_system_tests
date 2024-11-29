# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import logging
from pathlib import Path

from doubles.software_cameras import H264RtspCameraServer
from doubles.software_cameras import MjpegRtspCameraServer
from doubles.software_cameras import MultiPartJpegCameraServer

server_classes = {
    'http_mjpeg': MultiPartJpegCameraServer,
    'rtsp_mjpeg': MjpegRtspCameraServer,
    'rtsp_h264': H264RtspCameraServer,
    }

arg_parser = argparse.ArgumentParser(description="Software camera")
arg_parser.add_argument(
    '--type',
    choices=server_classes.keys(),
    default='http_mjpeg',
    help="Protocol; default: %(default)s")
arg_parser.add_argument(
    '--address',
    default='0.0.0.0',
    help="Bind address; default: %(default)s")
arg_parser.add_argument(
    '--port',
    type=int, default=0,
    help="Bind port; default: random (dynamic) port")
arg_parser.add_argument(
    '--user',
    help="User name for authentication")
arg_parser.add_argument(
    '--password',
    help="Password for authentication")
arg_parser.add_argument(
    '--debug', dest='logging_level',
    action='store_const', const=logging.DEBUG, default=logging.INFO,
    help="Logging level; default: INFO")
arg_parser.add_argument(
    '--h264-file',
    type=Path,
    help="H264-coded video file to stream")

if __name__ == '__main__':
    args = arg_parser.parse_args()
    server_args = {
        'address': args.address,
        'port': args.port,
        'user': args.user,
        'password': args.password,
        }
    if args.type == 'rtsp_h264':
        if args.h264_file is None:
            arg_parser.error("Option --h264-file must be specified if --type is rtsp_h264")
        server_args['source_video_file'] = args.h264_file
    logging.basicConfig(level=args.logging_level)
    logging.info("Press Ctrl+C to exit")
    try:
        with server_classes[args.type](**server_args) as server:
            server.serve()
    except KeyboardInterrupt:
        logging.info("Exit: Ctrl+C pressed")
        exit()
