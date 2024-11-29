# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from uuid import UUID

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import BadRequest
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool

_logger = logging.getLogger(__name__)


# The test has been added after https://networkoptix.atlassian.net/browse/VMS-13584 fix:
# mediaserver had an issue with removing layout with invalid empty typeId, after the fix
# mediaserver doesn't allow to create the layout.
def _test_invalid_layout_type_id(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    api = one_mediaserver.mediaserver().api
    if not distrib.newer_than('vms_5.1'):
        expected_error = "Invalid resource type"
    else:
        expected_error = "Invalid parameter `typeId`"
    try:
        api.add_layout("Layout_with_invalid_type", type_id=UUID(int=0))
    except BadRequest as e:
        if expected_error not in e.vms_error_string:
            raise
        _logger.info("Received error message %s contains expected message %s", e.vms_error_string, expected_error)
