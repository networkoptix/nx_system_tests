# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from datetime import timedelta
from typing import Set

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.ffprobe import video_is_valid
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.infra import Failure

_logger = logging.getLogger(__name__)


def _test_hls_output_with_duration_greater_than_recorded(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    artifacts_dir = get_run_dir()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    [camera] = add_cameras(mediaserver, camera_server)
    [period] = record_from_cameras(mediaserver.api, [camera], camera_server, 10)
    local_dir = artifacts_dir / 'stream-media-hls'
    local_dir.mkdir(parents=True, exist_ok=True)
    output_file = local_dir / 'output.mkv'
    extended_period = period.extend(timedelta(seconds=6000))
    stream_data = mediaserver.api.direct_download(camera.id, extended_period)
    assert stream_data
    output_file.write_bytes(stream_data)
    if installer_supplier.distrib().older_than('vms_6.0'):
        expected_transports = {'rtsp', 'mjpeg', 'webm'}
    else:
        expected_transports = {'rtsp', 'mjpeg', 'webm', 'webrtc'}
    check_media_stream_transports(mediaserver, expected_transports)
    assert video_is_valid(output_file), f"Failed integrity check: {output_file.name}"


# https://networkoptix.atlassian.net/browse/TEST-181
# transport check part (3):
def check_media_stream_transports(server, expected_transports: Set[str]):
    camera_info_list = server.api.http_get('ec2/getCamerasEx')
    assert camera_info_list  # At least one camera must be returned for following check to work
    for camera_info in camera_info_list:
        for add_params_rec in camera_info['addParams']:
            if add_params_rec['name'] == 'mediaStreams':
                value = json.loads(add_params_rec['value'])
                transports = set()
                for codec_rec in value['streams']:
                    transports |= set(codec_rec['transports'])
                _logger.info(
                    'Mediaserver %s returned following transports for camera %s: %s',
                    server, camera_info['physicalId'], ', '.join(sorted(transports)))
                # HLS is only supported for H264 and H265 codecs.
                assert transports == expected_transports, repr(transports)
                break
        else:
            raise Failure('ec2/getCamerasEx addParams element does not have "mediaStreams" record')
