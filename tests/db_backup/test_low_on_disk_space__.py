# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_backup_on_start_with_low_disk_space(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    # Free space must be lower than 10 GB for this test
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.stop()
    mediaserver.remove_database_backups()
    mediaserver.os_access.maintain_free_disk_space(9 * 1024**3)
    mediaserver.start()
    [backup] = wait_for_truthy(mediaserver.list_database_backups)
    # According to the spec https://networkoptix.atlassian.net/wiki/x/4IAlQ
    # the backup file, created when server start, should have `timer` at the
    # end of the name (backup filename format: ecs_{build}_{timestamp}_timer.db).
    assert backup.reason == 'timer'
