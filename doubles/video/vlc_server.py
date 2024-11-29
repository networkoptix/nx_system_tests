# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import ctypes.util
import logging
import os
import platform
import sys
import threading
import time
from contextlib import ExitStack
from contextlib import contextmanager

if os.name == 'nt':
    def _find_vlc_in_registry():
        import winreg
        for hive in winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER:
            try:
                key = winreg.OpenKey(hive, 'Software\\VideoLAN\\VLC')
                try:
                    install_dir, _ = winreg.QueryValueEx(key, 'InstallDir')
                finally:
                    winreg.CloseKey(key)
                return install_dir
            except winreg.error:
                continue
        [bits, _] = platform.architecture()
        raise Exception(
            f"Cannot find VLC installation in the registry; "
            f"use {bits} VLC with {bits} Python")

    def _try_preload_libvlc():
        install_dir = _find_vlc_in_registry()
        try:
            ctypes.CDLL(os.path.join(install_dir, 'libvlc.dll'))
        except FileNotFoundError:
            raise Exception(
                f"Cannot load VLC installation {install_dir}; "
                f"which was found in registry; "
                f"try reinstalling VLC")

    # python-vlc cannot load libvlc.dll on Windows 10 21H1
    # if the install dir can be found in the registry but not in PATH.
    # python-vlc changes the work dir and loads the DLL it by its name only,
    # but for unknown reasons Windows doesn't search the DLL there,
    # which is clearly seen in procmon output.
    # See: https://docs.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order#standard-search-order-for-desktop-applications  # noqa
    _try_preload_libvlc()

import vlc

_logger = logging.getLogger(__name__)

_log_level_vlc_to_python = {
    vlc.LogLevel.DEBUG: logging.DEBUG,
    vlc.LogLevel.NOTICE: logging.INFO,
    vlc.LogLevel.WARNING: logging.WARNING,
    vlc.LogLevel.ERROR: logging.ERROR,
    }
_libvlc_logger = logging.getLogger('libvlc')

try:
    _windll = ctypes.windll
except AttributeError:
    _c_lib = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
else:
    _c_lib = ctypes.windll.msvcrt

# Currently the binding in vlc module is buggy.
# See: https://github.com/oaubert/python-vlc/issues/25
_libvlc_log_get_context_type = ctypes.CFUNCTYPE(
    None, vlc.Log_ptr, ctypes.POINTER(ctypes.c_char_p),
    ctypes.POINTER(ctypes.c_char_p),
    ctypes.POINTER(ctypes.c_uint),
    )
_libvlc_log_get_context = _libvlc_log_get_context_type(
    ('libvlc_log_get_context', vlc.dll),
    ((1,), (2,), (2,), (2,)),  # 1 -- input param, 2 -- output param.
    )

_py_object_ptr = ctypes.POINTER(ctypes.py_object)


@vlc.CallbackDecorators.LogCb
def _log(data, level, ctx, fmt, args):
    message_buffer = ctypes.create_string_buffer(4096)
    _c_lib.vsprintf(message_buffer, fmt, ctypes.cast(args, ctypes.c_void_p))
    message = message_buffer.value.decode('utf8')
    module_name_raw, file_path_raw, line = _libvlc_log_get_context(ctx)
    module_logger = _libvlc_logger.getChild(module_name_raw.decode('utf8'))
    if file_path_raw is None:
        # Observed on Ubuntu 16.04 and VLC 2.2.2.
        file_path = None
        file_logger = module_logger
    else:
        # Observed on Debian 9 and VLC 3.0.7.
        file_path = os.fsdecode(file_path_raw)
        file_path_no_ext, _file_ext = os.path.splitext(file_path)
        file_logger_name = file_path_no_ext.replace(os.path.sep, '.')
        file_logger = module_logger.getChild(file_logger_name)
    level_python = _log_level_vlc_to_python[level]
    if file_logger.isEnabledFor(level_python):
        if data is not None:
            extra_ptr = ctypes.cast(data, _py_object_ptr)
            extra_py_object = extra_ptr.contents
            if extra_py_object:
                extra = extra_py_object.value
            else:
                # Object has been deleted.
                extra = None
        else:
            extra = None
        record = file_logger.makeRecord(
            file_logger.name, level_python,
            fn=file_path, lno=line,  # File name, line number.
            msg=message, args=(),
            exc_info=None,
            extra=extra,
            )
        file_logger.handle(record)


@contextmanager
def rtsp_serving(video_file, port, url_path, host_ip='', audio=False, user=None, password=None):
    # Retain data while libvlc is working.
    data = ctypes.py_object({'path': url_path, 'port': port})
    args = [
        str(video_file),
        # See: https://wiki.videolan.org/Documentation:Streaming_HowTo/Advanced_Streaming_Using_the_Command_Line  # NOQA
        # See: https://wiki.videolan.org/VLC_command-line_help
        # --sout-rtp-proto=tcp is not implemented; --rtsp-tcp (input) works.
        # The following are command line options without "--".
        'input-repeat=65535',  # Valid range is 0..65535, --loop doesn't work.
        'sout=#rtp{sdp=rtsp://%s:%d/%s}' % (host_ip, port, url_path),
        'sout-audio' if audio else 'no-sout-audio',
        'no-sout-spu',  # No sub-picture units (subtitles, menus etc.).
        'sout-keep',  # Keep all elementary streams
        ]
    if user is not None and password is not None:
        args = [*args, 'sout-rtsp-user %s' % user, 'sout-rtsp-pwd %s' % password]
    _logger.info("VLC: Args: %r", args)
    with ExitStack() as exit_stack:
        instance = vlc.Instance()
        _logger.debug("VLC: Instance: Initialize")
        exit_stack.callback(instance.release)
        exit_stack.callback(_logger.debug, "VLC: Instance: Release")
        _logger.debug("VLC: Instance: Set logging callback")
        instance.log_set(_log, ctypes.byref(data))
        media = instance.media_new(*args)
        exit_stack.callback(media.release)
        exit_stack.callback(_logger.debug, "VLC: Media: Release")
        _logger.debug("VLC: Player: Initialize")
        player = media.player_new_from_media()
        exit_stack.callback(player.release)
        exit_stack.callback(_logger.debug, "VLC: Player: Release")
        event_manager = player.event_manager()
        start_event = threading.Event()

        def cb(event):
            assert event.type == vlc.EventType.MediaPlayerPlaying
            start_event.set()

        event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, cb)
        exit_stack.callback(event_manager.event_detach, vlc.EventType.MediaPlayerPlaying)
        _logger.info("VLC: Player: Play")
        assert player.play() == 0
        exit_stack.callback(player.stop)
        exit_stack.callback(_logger.debug, "VLC: Player: Stop")
        start_timeout_sec = 1
        _logger.debug("VLC: Player: Wait until playing is started")
        if start_event.wait(start_timeout_sec) is None:
            raise RuntimeError("Playing hasn't started")
        _logger.debug("VLC: Player: Playing must be started")
        yield


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    try:
        path = sys.argv[1]
    except LookupError:
        print("Usage: {} <filename>".format(sys.argv[0]))
    else:
        with rtsp_serving(path, port=1025, url_path=os.path.basename(path)):
            while True:
                _logger.info("Streaming...")
                time.sleep(10)
