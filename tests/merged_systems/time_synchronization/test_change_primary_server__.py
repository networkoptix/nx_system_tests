# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.merged_systems.time_synchronization.common import configure_two_mediaservers_stand
from tests.merged_systems.time_synchronization.running_time import wait_until_mediaserver_and_os_time_sync
from tests.waiting import wait_for_truthy


def _test_change_primary_server(distrib_url, two_vm_types, api_version, exit_stack):
    """Change PRIMARY server, change time on its machine. Expect all servers align with it."""
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    configure_two_mediaservers_stand(two_mediaservers)
    old_primary = two_mediaservers.first.installation()
    old_secondary = two_mediaservers.second.installation()
    old_secondary.api.become_primary_time_server()
    wait_for_truthy(old_secondary.api.is_primary_time_server)
    new_primary, new_secondary = old_secondary, old_primary
    new_time = datetime.now(timezone.utc) + timedelta(hours=5)
    new_primary.os_access.set_datetime(new_time)
    wait_until_mediaserver_and_os_time_sync(new_primary.api, new_primary.os_access, timeout_sec=30)
    wait_until_mediaserver_and_os_time_sync(new_secondary.api, new_primary.os_access, timeout_sec=180)
