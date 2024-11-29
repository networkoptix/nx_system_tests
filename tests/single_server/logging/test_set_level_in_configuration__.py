# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.logging.common import LevelEnum
from tests.single_server.logging.common import less_severe_entries
from tests.single_server.logging.common import setup_server_and_trigger_logs


def _test_set_level_in_configuration(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    mediaserver.remove_logging_ini()

    def _test_log_level(log_level_str, expected_log_level):
        [api_log_level, entries] = setup_server_and_trigger_logs(mediaserver, log_level_str)
        assert api_log_level == expected_log_level.api_request
        assert not less_severe_entries(entries, expected_log_level.severity)

    _test_log_level('debug2', LevelEnum.VERBOSE)
    _test_log_level('verbose', LevelEnum.VERBOSE)
    _test_log_level('debug', LevelEnum.DEBUG)
    _test_log_level('info', LevelEnum.INFO)
    _test_log_level('warning', LevelEnum.WARNING)
    _test_log_level('error', LevelEnum.ERROR)
