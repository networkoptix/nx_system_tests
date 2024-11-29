# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_reserved_space(distrib_url, one_vm_type, disk_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    os = mediaserver.os_access
    one_mediaserver.hardware().add_disk(disk_type, 50 * 1024)
    small_path = os.mount_disk('S')
    [small] = api.list_storages(str(small_path), ignore_offline=True)
    one_mediaserver.hardware().add_disk(disk_type, 200 * 1024)
    medium_path = os.mount_disk('M')
    [medium] = api.list_storages(str(medium_path), ignore_offline=True)
    one_mediaserver.hardware().add_disk(disk_type, 350 * 1024)
    large_path = os.mount_disk('L')
    [large] = api.list_storages(str(large_path), ignore_offline=True)
    # Reserved space must be in range [10GB, 30GB] for X86, but not more
    # than 10-percent of total space.
    assert small.reserved_space == 10 * 1024**3  # Lower bound - 10 GB
    assert medium.reserved_space == int(medium.space * 0.1)  # 10-percent of total
    # VMS-52446: 30-percent upper bound removed
    assert large.reserved_space == int(large.space * 0.1)
