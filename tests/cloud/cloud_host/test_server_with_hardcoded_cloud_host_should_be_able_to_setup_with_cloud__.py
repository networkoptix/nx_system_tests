# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import MediaserverApiHttpError
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cloud.cloud_host.common import check_user_exists
from tests.infra import Failure


def _test_server_with_hardcoded_cloud_host_should_be_able_to_setup_with_cloud(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host)
    mediaserver.set_cloud_host(cloud_host)
    mediaserver.start()
    try:
        mediaserver.api.setup_cloud_system(cloud_account)
    except MediaserverApiHttpError as x:
        if x.vms_error_string == 'Could not connect to cloud: notAuthorized':
            raise Failure('Mediaserver is incompatible with this cloud host/customization')
        else:
            raise
    check_user_exists(mediaserver, is_cloud=True)
