# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_log_level_specific_values(distrib_url, one_vm_type, config_level, expected_level, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    mediaserver.remove_logging_ini()
    # The default value for this parameter is None, so there is no need to set it to None again.
    # When this parameter is set to None on Windows, it acts like removing parameter.
    # And if there is no such parameter, then an error occurs during removing.
    if config_level is not None:
        mediaserver.set_main_log_level(config_level)
    mediaserver.start()
    mediaserver.api.setup_local_system()
    assert mediaserver.api.http_get('api/logLevel', params={'name': 'MAIN'}) == expected_level
