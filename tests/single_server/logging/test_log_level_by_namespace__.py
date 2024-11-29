# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.logging.common import LevelEnum
from tests.single_server.logging.common import get_log_entries
from tests.single_server.logging.common import less_severe_entries


def _test_log_level_by_namespace(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    mediaserver.remove_logging_ini()
    mediaserver.set_main_log_level('info,debug[nx::network]')
    time.sleep(5)  # TODO: Poll the log for new entries, don't just sleep.
    mediaserver.start()
    entries = get_log_entries(mediaserver)
    assert entries
    debug_entries = less_severe_entries(entries, LevelEnum.INFO.severity)
    assert debug_entries
    # All entries with severity less than INFO should be in the `nx::network` namespace
    unexpected_entries = [
        entry for entry in debug_entries
        if not entry.tag.startswith('nx::network')
        ]
    assert not unexpected_entries
    mediaserver.stop()
    for log_file in mediaserver.list_log_files():
        log_file.unlink()
    mediaserver.set_main_log_level('info')
    mediaserver.start()
    time.sleep(5)  # TODO: Poll the log for new entries, don't just sleep.
    entries = get_log_entries(mediaserver)
    assert entries
    assert not less_severe_entries(entries, LevelEnum.INFO.severity)
