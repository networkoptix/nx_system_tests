# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from installation import install_vms_benchmark
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.infra import Failure


class test_ubuntu22_v0(VMSTest):
    """Test if rtsp_perf is able to load rtsp stream from saved archive.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_rtsp_perf_archive(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


def _test_rtsp_perf_archive(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    vms_benchmark_installation = install_vms_benchmark(one_mediaserver.os_access(), installer_supplier)
    server = one_mediaserver.mediaserver()

    # rtsp_perf loads archive data from random period in interval [now-60min - now-1min].
    # So start time now-30min will fit.
    [camera] = server.add_cameras_with_archive(
        sample_media_file=SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample.mkv')),
        start_times=[datetime.now(timezone.utc) - timedelta(minutes=30)],
        )
    server.api.rebuild_main_archive()

    credentials = server.api.get_credentials()
    username = credentials.username
    password = credentials.password
    rtsp_url = 'rtsp://127.0.0.1:{}/{}'.format(server.port, camera.id)
    timeout_sec = 60
    started_at = time.monotonic()
    rtsp_process = vms_benchmark_installation.start_rtsp_perf_archive(
        [rtsp_url], username, password)
    while True:
        rtsp_perf_statistics = next(rtsp_process)
        if rtsp_perf_statistics.bitrate_mbps > 0.1:
            break
        if time.monotonic() - started_at > timeout_sec:
            raise Failure("rtsp_perf did not start")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_v0()]))
