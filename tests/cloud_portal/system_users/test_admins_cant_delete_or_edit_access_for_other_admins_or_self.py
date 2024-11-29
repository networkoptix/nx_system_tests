# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api._cloud import CloudAccount
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from installation import public_ip_check_addresses
from mediaserver_api import Groups
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_left_menu import AddUserModal
from tests.cloud_portal._system_left_menu import UsersDropdown
from tests.cloud_portal._system_users import PermissionsDropdown
from tests.cloud_portal._system_users import SystemUsers
from vm.networks import setup_flat_network


class test_admins_cant_delete_or_edit_access_for_other_admins_or_self(VMSTest, CloudTest):
    """Test Administrators or Power Users can't delete themselves or each other.

    Verifies that deletion and permissions changes of other Administrators,
    Owners or Power Users are prohibited.
    Selection-Tag: 41904
    Selection-Tag: 41905
    Selection-Tag: cloud_portal
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/41904
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/41905
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        server_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        cloud_owner = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [server_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver = server_stand.mediaserver()
        mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses],
            )
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.setup_cloud_system(cloud_owner)
        cloud_admin_1 = cloud_account_factory.create_account()
        cloud_admin_2 = cloud_account_factory.create_account()
        if installer_supplier.distrib().newer_than("vms_5.1"):
            _add_power_user_to_mediaserver(cloud_admin_1, mediaserver)
            _add_power_user_to_mediaserver(cloud_admin_2, mediaserver)
        else:
            _add_admin_user_to_mediaserver(cloud_admin_1, mediaserver)
            _add_admin_user_to_mediaserver(cloud_admin_2, mediaserver)
        cloud_viewer = cloud_account_factory.create_account()
        mediaserver.api.add_cloud_user(
            name=cloud_viewer.user_email,
            email=cloud_viewer.user_email,
            permissions=Permissions.VIEWER_PRESET,
            )
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'Admins_cant_edit_admins_or_self_{time.perf_counter_ns()}'
        cloud_owner.rename_system(system_id, system_name)
        browser = exit_stack.enter_context(browser_stand.browser())
        url = f"https://{cloud_host}/systems/{system_id}"
        browser.open(url)
        LoginComponent(browser).login(cloud_admin_1.user_email, cloud_admin_1.password)
        SystemAdministrationPage(browser).wait_for_page_to_be_ready()
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        # Verify the Remove button and permissions dropdown appear when expected to avoid
        # False-Positive results while checking their expected absence.
        users_dropdown.get_user_with_email(cloud_viewer.user_email).invoke()
        assert element_is_present(SystemUsers(browser).remove_user_button)
        assert element_is_present(PermissionsDropdown(browser).get_permissions_dropdown_button)
        users_dropdown.get_user_with_email(cloud_owner.user_email).invoke()
        assert not element_is_present(SystemUsers(browser).remove_user_button)
        assert not element_is_present(PermissionsDropdown(browser).get_permissions_dropdown_button)
        users_dropdown.get_user_with_email(cloud_admin_1.user_email).invoke()
        assert not element_is_present(SystemUsers(browser).remove_user_button)
        assert not element_is_present(PermissionsDropdown(browser).get_permissions_dropdown_button)
        # Bug with VMS 6.0 where a Power User can remove another Power User.
        # See: https://networkoptix.atlassian.net/issues/CLOUD-14255
        users_dropdown.get_user_with_email(cloud_admin_2.user_email).invoke()
        assert not element_is_present(SystemUsers(browser).remove_user_button)
        assert not element_is_present(PermissionsDropdown(browser).get_permissions_dropdown_button)
        users_dropdown.add_user_button().invoke()
        expected_error = f"This email has already been registered in the {system_name} system"
        add_user_modal = AddUserModal(browser)
        add_user_modal.input_email_for_new_user(cloud_owner.user_email)
        add_user_modal.get_add_user_button().invoke()
        error_text = add_user_modal.get_error_text()
        assert expected_error in error_text
        add_user_modal.get_close_button().invoke()
        users_dropdown.add_user_button().invoke()
        add_user_modal_2 = AddUserModal(browser)
        add_user_modal_2.input_email_for_new_user(cloud_admin_1.user_email)
        add_user_modal_2.get_add_user_button().invoke()
        error_text_2 = add_user_modal_2.get_error_text()
        assert expected_error in error_text_2
        add_user_modal_2.get_close_button().invoke()
        users_dropdown.add_user_button().invoke()
        add_user_modal_3 = AddUserModal(browser)
        add_user_modal_3.input_email_for_new_user(cloud_admin_2.user_email)
        add_user_modal_3.get_add_user_button().invoke()
        error_text_3 = add_user_modal_3.get_error_text()
        assert expected_error in error_text_3


def _add_power_user_to_mediaserver(user: CloudAccount, mediaserver: Mediaserver):
    mediaserver.api.add_cloud_user(
        name=user.user_email,
        email=user.user_email,
        group_id=Groups.POWER_USERS,
        )


def _add_admin_user_to_mediaserver(user: CloudAccount, mediaserver: Mediaserver):
    mediaserver.api.add_cloud_user(
        name=user.user_email,
        email=user.user_email,
        permissions=[Permissions.ADMIN],
        )


if __name__ == '__main__':
    exit(test_admins_cant_delete_or_edit_access_for_other_admins_or_self().main())
