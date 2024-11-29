# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api._imap import IMAPConnection
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Groups
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from vm.networks import setup_flat_network


class test_share_with_registered_user_sends_notification(VMSTest, CloudTest):
    """Test share with registered user sends notification.

    Selection-Tag: 41888
    Selection-Tag: 30446
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41888
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30446
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        distrib_url = args.distrib_url
        one_vm_type = 'ubuntu22'
        api_version = 'v2'
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
        stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
        mediaserver = stand.mediaserver()
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        services_hosts = cloud_owner.get_services_hosts()
        mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver_api = stand.api()
        mediaserver_api.setup_cloud_system(cloud_owner)
        cloud_system_id = mediaserver_api.get_cloud_system_id()
        cloud_viewer = exit_stack.enter_context(cloud_account_factory.temp_account())
        cloud_viewer.set_user_customization(customization_name)
        cloud_owner.share_system(
            cloud_system_id, cloud_viewer.user_email, user_groups=[Groups.VIEWERS])
        with IMAPConnection(*cloud_account_factory.get_imap_credentials()) as imap_connection:
            subject = f"Video system {mediaserver_api.get_system_name()} was shared with you"
            message_id = imap_connection.get_message_id_by_subject(cloud_viewer.user_email, subject)
            assert imap_connection.has_link_to_cloud_instance_in_message(message_id, cloud_host)
            link_to_system_page = imap_connection.get_link_to_cloud_system(message_id)
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(link_to_system_page)
        LoginComponent(browser).login(cloud_viewer.user_email, cloud_viewer.password)
        assert element_is_present(HeaderNav(browser).account_dropdown)


if __name__ == '__main__':
    exit(test_share_with_registered_user_sends_notification().main())
