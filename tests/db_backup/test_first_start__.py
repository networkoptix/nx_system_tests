# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_backup_on_first_start(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.remove_database_backups()
    mediaserver.start()
    [backup] = mediaserver.wait_for_database_backups()
    backup_marker = mediaserver.api.get_datetime().timestamp()
    assert backup.suffix == '.db'
    assert backup.prefix == 'ecs'
    assert backup.build == mediaserver.api.get_version().build
    assert math.isclose(backup.timestamp_sec, backup_marker, abs_tol=7)
    assert backup.reason == 'timer'
