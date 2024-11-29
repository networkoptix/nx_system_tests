# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import generate_layout
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool

_logger = logging.getLogger(__name__)


def _test_save_and_remove_layout(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    manual_layout_id = mediaserver.api.add_layout('Layout_1')
    mediaserver.api.get_layout(manual_layout_id)
    mediaserver.api.remove_layout(manual_layout_id)
    assert mediaserver.api.get_layout(manual_layout_id) is None
    generated_layout = generate_layout(index=1)
    generated_layout_id = mediaserver.api.add_generated_layout(generated_layout)
    mediaserver.api.get_layout(generated_layout_id)
    mediaserver.api.remove_layout(generated_layout_id)
    assert mediaserver.api.get_layout(generated_layout_id) is None
