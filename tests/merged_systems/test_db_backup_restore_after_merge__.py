# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re

from ca import default_ca
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import log_full_info_diff
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access import copy_file
from tests.infra import Failure

_logger = logging.getLogger(__name__)


def _test_servers_backed_up_before_merge(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    artifacts_dir = get_run_dir()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    before_one = one.api.get_full_info()
    before_two = two.api.get_full_info()
    # Remove all backup files to ensure new backup creates after merge
    one.remove_database_backups()
    two.remove_database_backups()
    merge_systems(one, two, take_remote_settings=False)
    one.stop()
    two.stop()
    # Restore mediaserver's database from latest backup, auto-created before merge
    for server in one, two:
        backup_files = server.list_database_backups()
        _logger.debug('{} backup files: {}'.format(server, backup_files))
        try:
            [backup_file] = backup_files
        except ValueError:
            message = "Expected exactly one backup file on {}, got: {}".format(
                server, backup_files)
            raise Failure(message)
        backup_artifact_name = '{}-{}'.format(server, backup_file.filename())
        copy_file(backup_file.path, artifacts_dir / backup_artifact_name)
        server.remove_database()
        server.remove_database_backups()
        server.init_key_pair(default_ca().generate_key_and_cert(server.os_access.address))
        copy_file(artifacts_dir / backup_artifact_name, server.ecs_db)
        server.api.use_local_auth()
        server.start()

    def full_info_diff(server, initial_full_info):
        current_full_info = server.api.get_full_info()
        diff_list = current_full_info.diff(initial_full_info)
        # Mediaserver stores its private key in the database. Since the clean_up method was called,
        # it was removed and a new one was created. Thus, the certificate should be ignored here.
        expected_diffs = [
            r'servers/[a-zA-Z0-9-]*/parameters/certificate',
            r'servers/[a-zA-Z0-9-]*/parameters/userProvidedCertificate',
            ]
        expected_diffs = '|'.join(expected_diffs)
        diff_list = {k: v for k, v in diff_list.items() if not re.match(expected_diffs, k)}
        if diff_list:
            _logger.info("%r has non-empty full info diff:", server)
            log_full_info_diff(_logger.info, diff_list)
        return diff_list

    full_info_diff_one = full_info_diff(one, before_one)
    full_info_diff_two = full_info_diff(two, before_two)

    assert not full_info_diff_one, f'{one!r} has unexpected full info diff'
    assert not full_info_diff_two, f'{two!r} has unexpected full info diff'
