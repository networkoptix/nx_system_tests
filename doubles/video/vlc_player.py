# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
from pathlib import Path

_logger = logging.getLogger(__name__)


class VLCPlayer:

    def __init__(self, os_access):
        self.os_access = os_access

    def _get_app_launcher_path(self) -> Path:
        path = self.os_access.path(r'C:\Program Files\VideoLAN\VLC\vlc.exe')
        if path.exists():
            return path
        raise RuntimeError('VLC Player not found. Make sure VLC Player is installed.')

    def get_preview(self, file_path: Path) -> Path:
        if not file_path.exists():
            raise Exception(f"File not found: {file_path}")
        tmp = file_path.with_suffix(file_path.name + '.snapshots')
        tmp.mkdir(exist_ok=True)
        app_dir = self._get_app_launcher_path()
        outcome = self.os_access.run([
            str(app_dir),
            str(file_path),
            '--start-time=0',
            '--stop-time=0.1',
            '--play-and-exit',
            '--video-filter=scene',
            f'--scene-path={tmp}',
            '--vout=vdummy',
            '--intf=dummy',
            re.sub(r'\n\s*', '', '''
                #transcode{
                    vfilter=scene{
                        sprefix=%(stem)s,
                        sformat=png
                        },
                    vcodec=copy,
                    acodec=none
                    }
                :standard{
                    access=file,
                    dst=%(parent)s\\redirect.mp4
                    }
            ''') % {
                'stem': file_path.stem,
                'parent': file_path.parent,
                },
            ])
        stderr = outcome.stderr.decode('UTF-8')
        assert outcome.returncode == 0, stderr
        snapshots = self.os_access.path(tmp).glob('*')
        snapshots_names = [snapshot.name for snapshot in snapshots]
        if len(snapshots_names) <= 0:
            raise Exception("VLC player snapshot creation failed.")
        return tmp / snapshots_names[0]
