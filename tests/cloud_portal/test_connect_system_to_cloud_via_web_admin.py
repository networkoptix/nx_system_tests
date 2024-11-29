# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.html_elements import InputField
from browser.webdriver import Browser
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._login import ConnectSystemToCloudComponent
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.web_admin._login import LoginForm
from tests.web_admin._nx_cloud import ConnectToCloudModal
from tests.web_admin._nx_cloud import NxCloudForm
from vm.networks import setup_flat_network


class test_connect_system_to_cloud_via_web_admin(VMSTest, CloudTest):
    """Test connect system to Cloud via WebAdmin.

    Selection-Tag: 122103
    Selection-Tag: cloud_portal
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/122103
    """

    # TODO: Figure out where to put such integration tests that test multiple components.
    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        server_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        cloud_account = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_account.set_user_customization(customization_name)
        services_hosts = cloud_account.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        [[address, _], _] = setup_flat_network(
            [server_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver = server_stand.mediaserver()
        mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.setup_local_system()
        mediaserver_user = mediaserver.api.get_credentials()
        browser = exit_stack.enter_context(browser_stand.browser())
        mediaserver_web_url = mediaserver.url(address)
        browser.open(mediaserver_web_url)
        login_form = LoginForm(browser)
        login_form.get_login_field().put(mediaserver_user.username)
        login_form.get_password_field().put(mediaserver_user.password)
        login_form.get_submit_button().invoke()
        web_admin_cloud_form = NxCloudForm(browser)
        web_admin_cloud_form.get_connect_to_cloud_button().invoke()
        _select_newly_open_tab(browser, expected_tab_count=2)
        cloud_login_component = LoginComponent(browser)
        cloud_login_component.get_accept_risk_link().invoke()
        cloud_login_component.login(cloud_account.user_email, cloud_account.password)
        if installer_supplier.distrib().newer_than('vms_5.1'):
            web_admin_connect_to_cloud = ConnectSystemToCloudComponent(browser)
            assert element_is_present(web_admin_connect_to_cloud.get_connect_system_label)
            assert web_admin_connect_to_cloud.get_user_email() == cloud_account.user_email
            web_admin_connect_to_cloud.connect()
        [web_admin_tab, _cloud_portal_tab] = browser.get_tabs()
        web_admin_tab.switch_to()
        web_admin_connect_to_cloud_modal = ConnectToCloudModal(browser)
        # TODO: Update when mechanics to get Cloud instance name is implemented.
        expected_title = "Connect System to Nx Cloud"
        assert _modal_title_contains(
            expected_title,
            web_admin_connect_to_cloud_modal,
            timeout=10,
            ), f"{expected_title!r} is not in the modal"
        password_field = web_admin_connect_to_cloud_modal.get_password_input_field()
        _wait_active_input_field(password_field, timeout=5)
        password_field.put(mediaserver_user.password)
        web_admin_connect_to_cloud_modal.get_connect_button().invoke()
        assert web_admin_cloud_form.system_has_connected_label()
        assert element_is_present(web_admin_cloud_form.get_disconnect_from_cloud_button)
        assert "Owner – you" == web_admin_cloud_form.get_owner_text()
        browser.open(f"https://{cloud_host}/systems")
        LoginComponent(browser).login(cloud_account.user_email, cloud_account.password)
        system_administration_page = SystemAdministrationPage(browser)
        system_administration_page.wait_for_system_name_field(timeout=90)
        _wait_until_owner_text_changes(
            system_administration_page,
            new_text="Owner – you(change)",
            timeout=20,
            )
        assert element_is_present(system_administration_page.get_change_system_name_button)
        assert element_is_present(system_administration_page.get_merge_with_another_system_button)
        assert element_is_present(system_administration_page.get_disconnect_from_cloud_button)


def _select_newly_open_tab(browser: Browser, expected_tab_count: int):
    started_at = time.monotonic()
    while True:
        tabs = browser.get_tabs()
        if len(tabs) == expected_tab_count:
            tabs[-1].switch_to()
            return
        if time.monotonic() - started_at > 10:
            raise RuntimeError(f"Wrong number of tabs. Expected {expected_tab_count}, got {len(tabs)}")


def _wait_until_owner_text_changes(
        system_administration: SystemAdministrationPage,
        new_text: str,
        timeout: float,
        ):
    started_at = time.monotonic()
    end_time = started_at + timeout
    while True:
        current_text = system_administration.get_owner_text()
        if current_text == new_text:
            break
        if time.monotonic() > end_time:
            raise RuntimeError(
                f"Owner text is not updated in {timeout} seconds. "
                f"Expected {new_text}, got {current_text}")
        time.sleep(0.3)


def _wait_active_input_field(input_field: InputField, timeout: float):
    # Field may not be active instantly after it is loaded.
    started_at = time.monotonic()
    while True:
        if input_field.is_active():
            return
        if time.monotonic() - started_at > timeout:
            raise RuntimeError(
                f"Password input field is not active within {timeout} second timeout")
        time.sleep(0.5)


def _modal_title_contains(title_text: str, modal: ConnectToCloudModal, timeout: float) -> bool:
    started_at = time.monotonic()
    while True:
        if title_text in modal.get_title_text():
            return True
        if time.monotonic() - started_at > timeout:
            return False
        time.sleep(0.5)


if __name__ == '__main__':
    exit(test_connect_system_to_cloud_via_web_admin().main())
