# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from uuid import UUID

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import generate_server_guid
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool

_logger = logging.getLogger(__name__)


def _test_change_local_system_id(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    one.api.wait_for_neighbors_status('Online')
    two.api.wait_for_neighbors_status('Online')
    new_local_system_id = generate_server_guid(1)
    one.api.set_local_system_id(new_local_system_id)
    assert one.api.get_local_system_id() == UUID(new_local_system_id)
    one.api.wait_for_neighbors_status('Offline')
    two.api.wait_for_neighbors_status('Offline')
