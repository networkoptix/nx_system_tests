# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.external_storages.smb_stand import smb_stand
from tests.infra import Failure


def _test_no_password_in_logs_and_db(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    smb_credentials = ('', '')  # Create a share with enabled anonymous access
    stand = smb_stand(two_vm_types, pool, exit_stack, smb_credentials)
    api = stand.mediaserver().api
    address = stand.smb_address()
    tree = stand.smb_share_name()
    password = 'BadPassword'
    api.add_smb_storage(address, tree, username='BadUser', password=password)
    if _password_in_logs(stand.mediaserver(), password):
        raise Failure("Entered password is presented in logs")
    if _password_in_db(stand.mediaserver(), password):
        raise Failure("Entered password is presented in database")


def _password_in_logs(mediaserver, password):
    [log_file] = mediaserver.list_log_files('log_file_verbose.log')
    for line in log_file.read_text('utf-8').splitlines():
        if password in line:
            return True
    return False


def _password_in_db(mediaserver, password):
    return password.encode('ascii') in mediaserver.ecs_db.read_bytes()
