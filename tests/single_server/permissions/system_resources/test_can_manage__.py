# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Permissions
from mediaserver_api import SYSTEM_ADMIN_USER_ID
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_can_manage(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    system_resource = 'Resource_created_by_system_admin'
    mediaserver.api.http_post('ec2/setResourceParams', [{
        'resourceId': f'{SYSTEM_ADMIN_USER_ID}',
        'name': system_resource,
        'value': 'Value',
        }])
    if not mediaserver.newer_than('vms_5.1'):
        # The solution with groups doesn't work on old versions.
        test_admin = mediaserver.api.add_local_user(
            'test_admin', 'WellKnownPassword2', permissions=[Permissions.ADMIN])
    else:
        test_admin_group = mediaserver.api.add_user_group('test_admin_group', [Permissions.ADMIN])
        test_admin = mediaserver.api.add_local_user(
            'test_admin', 'WellKnownPassword2', group_id=test_admin_group)
    mediaserver_api_for_actor = mediaserver.api.as_user(test_admin)
    # Add system resources
    resource_created_by_user = 'resource_created_by_user_admin'
    mediaserver_api_for_actor.http_post('ec2/setResourceParams', [{
        'resourceId': f'{SYSTEM_ADMIN_USER_ID}',
        'name': resource_created_by_user,
        'value': '',
        }])
    # Remove system resources
    mediaserver_api_for_actor.http_post('ec2/removeResourceParam', dict(
        resourceId=SYSTEM_ADMIN_USER_ID, name=system_resource))
