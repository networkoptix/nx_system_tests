# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_left_menu import AddUserModal
from tests.cloud_portal._system_left_menu import UsersDropdown
from vm.networks import setup_flat_network


class test_add_user_email_validation(VMSTest, CloudTest):
    """Test add user modal email input validation.

    Selection-Tag: 78227
    Selection-Tag: 41902
    Selection-Tag: 47296
    Selection-Tag: cloud_portal
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/78227
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/41902
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/47296
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
        cloud_owner = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        services_hosts = cloud_owner.get_services_hosts()
        mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver.start()
        mediaserver_api = stand.api()
        mediaserver_api.setup_cloud_system(cloud_owner)
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'Add_user_email_validation_{time.perf_counter_ns()}'
        cloud_owner.rename_system(system_id, system_name)
        browser = exit_stack.enter_context(browser_stand.browser())
        link = f"https://{cloud_host}/systems/{mediaserver_api.get_cloud_system_id()}"
        browser.open(link)
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        SystemAdministrationPage(browser).wait_for_system_name_field(timeout=90)
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        users_dropdown.add_user_button().invoke()
        add_user_modal = AddUserModal(browser)
        expected_error = 'Email is required'
        add_user_modal.input_email_for_new_user('')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user(' ')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        expected_error = 'Please enter a valid Email'
        add_user_modal.input_email_for_new_user('noptixqagmail.com')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('@gmail.com')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('noptixqa@gmail..com')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('noptixqa@192.168.1.1.0')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('noptixqa.@gmail.com')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('noptixq..a@gmail.c')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('noptixqa@-gmail.com')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('myemail')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('myemail@')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('myemail@gmail')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('myemail@.com')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('my@email@gmail.com')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('myemail@ gmail.com')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user('myemail@gmail.com;')
        add_user_modal.get_add_user_button().invoke()
        assert expected_error in add_user_modal.get_error_text()
        add_user_modal.input_email_for_new_user(' myemail@gmail.com')
        assert not element_is_present(add_user_modal.get_error_text)
        add_user_modal.input_email_for_new_user('myemail@gmail.com ')
        assert not element_is_present(add_user_modal.get_error_text)
        add_user_modal.input_email_for_new_user('myemail@gmail.com')
        assert not element_is_present(add_user_modal.get_error_text)


if __name__ == '__main__':
    exit(test_add_user_email_validation().main())
