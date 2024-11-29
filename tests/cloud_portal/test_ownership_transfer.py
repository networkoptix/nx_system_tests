# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api._cloud import CloudAccount
from cloud_api.cloud import ensure_flags_enabled
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
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_administration_page import TransferOwnershipModal
from tests.cloud_portal._system_left_menu import UsersDropdown
from vm.networks import setup_flat_network


class test_ownership_transfer(VMSTest, CloudTest):
    """Test ownership transfer.

    Selection-Tag: 121008
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/121008
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        ensure_flags_enabled(cloud_host, ['newHeader'])
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        mediaserver = stand.mediaserver()
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_initial_owner = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_initial_owner.set_user_customization(customization_name)
        services_hosts = cloud_initial_owner.get_services_hosts()
        mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver.start()
        mediaserver.api.setup_cloud_system(cloud_initial_owner)
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'Tile_test_system_{int(time.perf_counter_ns())}'
        cloud_initial_owner.rename_system(system_id, system_name)
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_second_owner = cloud_account_factory.create_account()
        cloud_second_owner.set_user_customization(customization_name)
        cloud_admin_not_owner = cloud_account_factory.create_account()
        cloud_admin_not_owner.set_user_customization(customization_name)
        if installer_supplier.distrib().newer_than("vms_5.1"):
            _add_power_user_to_mediaserver(cloud_second_owner, mediaserver)
            _add_power_user_to_mediaserver(cloud_admin_not_owner, mediaserver)
        else:
            _add_admin_user_to_mediaserver(cloud_second_owner, mediaserver)
            _add_admin_user_to_mediaserver(cloud_admin_not_owner, mediaserver)
        browser = exit_stack.enter_context(browser_stand.browser())
        link = f"https://{args.cloud_host}/systems/"
        browser.open(link)
        login_component = LoginComponent(browser)
        login_component.login(cloud_initial_owner.user_email, cloud_initial_owner.password)
        system_administration = SystemAdministrationPage(browser)
        system_administration.wait_for_page_to_be_ready()
        system_administration.click_change_ownership()
        second_owner_email = cloud_second_owner.user_email
        transfer_ownership = TransferOwnershipModal(browser)
        transfer_ownership.input_email_of_new_owner(second_owner_email)
        transfer_ownership.click_next()
        confirmation_block = transfer_ownership.get_confirmation_text()
        missing_email_error = f"{second_owner_email!r} not in {confirmation_block!r}"
        assert second_owner_email in confirmation_block, missing_email_error
        assert element_is_present(transfer_ownership.get_warning_text)
        transfer_ownership.click_transfer()
        transfer_ownership.wait_for_request_has_been_sent_text()
        transfer_ownership.close_by_ok()
        header = HeaderNav(browser)
        header.account_dropdown().invoke()
        account_dropdown = AccountDropdownMenu(browser)
        account_dropdown.log_out_option().invoke()
        browser.open(link)
        login_component.login(cloud_second_owner.user_email, cloud_second_owner.password)
        system_administration = SystemAdministrationPage(browser)
        system_administration.wait_for_page_to_be_ready()
        ownership_text = (
            f"{cloud_initial_owner.get_user_info().get_full_name()} "
            f"({cloud_initial_owner.user_email}) "
            f"wants to transfer ownership of this system to you")
        # Redirect to Ownership transfer does not work in ChromeDriver, expected text does not appear.
        # See: https://networkoptix.atlassian.net/browse/CLOUD-13341
        assert system_administration.get_ownership_transfer_text() == ownership_text
        system_administration.accept_ownership_transfer()
        assert system_administration.get_owner_text() == "Owner – you(change)"
        header.account_dropdown().invoke()
        account_dropdown.log_out_option().invoke()
        browser.open(link)
        login_component.login(cloud_initial_owner.user_email, cloud_initial_owner.password)
        system_administration = SystemAdministrationPage(browser)
        assert element_is_present(system_administration.get_no_systems_text)
        header.account_dropdown().invoke()
        account_dropdown.log_out_option().invoke()
        browser.open(link)
        login_component.login(cloud_admin_not_owner.user_email, cloud_admin_not_owner.password)
        system_administration = SystemAdministrationPage(browser)
        system_administration.wait_for_page_to_be_ready()
        owner_text = f"Owner – FT Account For default customization ({cloud_second_owner.user_email})"
        # Redirect to Ownership transfer does not work in ChromeDriver, expected text does not appear.
        # See: https://networkoptix.atlassian.net/browse/CLOUD-13341
        assert system_administration.get_owner_text() == owner_text
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        assert users_dropdown.has_user_with_email(cloud_second_owner.user_email)
        assert not users_dropdown.has_user_with_email(cloud_initial_owner.user_email)


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
    exit(test_ownership_transfer().main())
