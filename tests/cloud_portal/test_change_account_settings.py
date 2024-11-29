# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import make_cloud_account_factory
from tests.base_test import CloudTest
from tests.cloud_portal._account_settings import AccountInformation
from tests.cloud_portal._account_settings import AccountLanguageDropDown
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._toast_notification import CookieBanner
from tests.cloud_portal._toast_notification import SuccessToast
from tests.cloud_portal._translation import de_de
from tests.cloud_portal._translation import en_us


class test_change_account_settings(CloudTest):
    """Test change account settings.

    Selection-Tag: 94720
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/94720
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        ensure_flags_enabled(cloud_host, ['newHeader'])
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = cloud_account_factory.create_account()
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f'https://{cloud_host}')
        header = HeaderNav(browser, en_us)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        header.wait_until_ready()
        banner = CookieBanner(browser)
        if banner.is_visible():
            banner.close()
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).account_settings_option().invoke()
        account_information = AccountInformation(browser)
        first_name_field = account_information.first_name_field()
        last_name_field = account_information.last_name_field()
        full_name = cloud_owner.get_user_info().get_full_name()
        first_name = first_name_field.get_value()
        last_name = last_name_field.get_value()
        assert full_name == f"{first_name} {last_name}"
        updated_name = 'UpdatedName'
        updated_last_name = 'UpdatedLastName'
        first_name_field.clear()
        first_name_field.put(updated_name)
        last_name_field.clear()
        last_name_field.put(updated_last_name)
        AccountLanguageDropDown(browser).select_language('Deutsch')
        german_account_settings = AccountInformation(browser, de_de)
        assert german_account_settings.cancel_button().is_active()
        german_account_settings.save()
        success_toast = SuccessToast(browser)
        assert success_toast.get_text() == de_de.tr("ACCOUNT_SAVED")
        full_name_changed = cloud_owner.get_user_info().get_full_name()
        first_name = first_name_field.get_value()
        last_name = last_name_field.get_value()
        [first_name_api, last_name_api] = full_name_changed.split()
        assert full_name_changed == f"{first_name} {last_name}"
        assert first_name_api == updated_name
        assert last_name_api == updated_last_name


if __name__ == '__main__':
    exit(test_change_account_settings().main())
