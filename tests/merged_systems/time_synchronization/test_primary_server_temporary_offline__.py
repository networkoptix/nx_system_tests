# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.merged_systems.time_synchronization.common import configure_two_mediaservers_stand
from tests.merged_systems.time_synchronization.running_time import mediaserver_and_os_time_are_in_sync


def _test_primary_server_temporary_offline(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    configure_two_mediaservers_stand(two_mediaservers)
    primary = two_mediaservers.first.installation()
    secondary = two_mediaservers.second.installation()
    primary.stop()
    secondary.os_access.set_datetime(datetime.now(timezone.utc) + timedelta(hours=4))
    time.sleep(10)
    assert mediaserver_and_os_time_are_in_sync(secondary.api, primary.os_access)
    # TODO: somehow pass the fact that stopped primary is OK and remove following line
    primary.start()
