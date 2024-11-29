# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.chrome.provisioned_chrome import chrome_stand
from browser.nx_colors import ERROR_RED
from cloud_api.cloud import make_cloud_account_factory
from tests.base_test import CloudTest
from tests.cloud_portal._change_pass import ChangePassForm
from tests.cloud_portal._change_pass import PasswordBadge
from tests.cloud_portal._change_pass import PasswordTooltip
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._translation import en_us


class test_invalid_new_passwords(CloudTest):
    """Test invalid new passwords.

    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_gitlab
    Selection-Tag: cloud_portal_smoke
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        language = en_us
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host]))
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f"https://{cloud_host}/")
        header = HeaderNav(browser)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        header.wait_until_ready()
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).change_password_option().invoke()
        change_pass_form = ChangePassForm(browser)
        current_password_input = change_pass_form.current_password_input()
        current_password_input.set_password(cloud_owner.password)
        new_password_input = change_pass_form.new_password_input()
        short_password = 'asdqwe1'
        new_password_input.set_password(short_password)
        current_password_input.focus()
        short_badge = PasswordBadge(browser)
        assert short_badge.get_text() == language.tr('PASSWORD_TOO_SHORT_BADGE')
        short_badge.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_TOO_SHORT_TOOLTIP')
        assert new_password_input.is_encircled_by(ERROR_RED)
        cyrillic_password = 'Кенгшщзх'
        new_password_input.set_password(cyrillic_password)
        current_password_input.focus()
        incorrect_badge = PasswordBadge(browser)
        assert incorrect_badge.get_text() == language.tr('PASSWORD_INCORRECT_BADGE')
        incorrect_badge.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_SPECIAL_CHARS')
        assert new_password_input.is_encircled_by(ERROR_RED)
        smiley_password = '☠☿☂⊗⅓∠∩λ℘웃♞⊀☻★'
        new_password_input.set_password(smiley_password)
        current_password_input.focus()
        incorrect_badge_2 = PasswordBadge(browser)
        assert incorrect_badge_2.get_text() == language.tr('PASSWORD_INCORRECT_BADGE')
        incorrect_badge_2.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_SPECIAL_CHARS')
        assert new_password_input.is_encircled_by(ERROR_RED)
        glyph_password = '您都可以享受源源不あなたのアカウント'
        new_password_input.set_password(glyph_password)
        current_password_input.focus()
        incorrect_badge_3 = PasswordBadge(browser)
        assert incorrect_badge_3.get_text() == language.tr('PASSWORD_INCORRECT_BADGE')
        incorrect_badge_3.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_SPECIAL_CHARS')
        assert new_password_input.is_encircled_by(ERROR_RED)
        tm_password = 'PasswordWithUnusualSymbols®™'
        new_password_input.set_password(tm_password)
        current_password_input.focus()
        incorrect_badge_4 = PasswordBadge(browser)
        assert incorrect_badge_4.get_text() == language.tr('PASSWORD_INCORRECT_BADGE')
        incorrect_badge_4.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_SPECIAL_CHARS')
        assert new_password_input.is_encircled_by(ERROR_RED)
        password_with_prefixed_spaces = "  PrefixedSpaces"
        new_password_input.set_password(password_with_prefixed_spaces)
        current_password_input.focus()
        incorrect_badge_5 = PasswordBadge(browser)
        assert incorrect_badge_5.get_text() == language.tr('PASSWORD_INCORRECT_BADGE')
        incorrect_badge_5.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_SPECIAL_CHARS')
        assert new_password_input.is_encircled_by(ERROR_RED)
        password_with_postfixed_spaces = "PostfixedSpaces  "
        new_password_input.set_password(password_with_postfixed_spaces)
        current_password_input.focus()
        incorrect_badge_6 = PasswordBadge(browser)
        assert incorrect_badge_6.get_text() == language.tr('PASSWORD_INCORRECT_BADGE')
        incorrect_badge_6.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_SPECIAL_CHARS')
        assert new_password_input.is_encircled_by(ERROR_RED)
        lowercase_password = "lowercase"
        new_password_input.set_password(lowercase_password)
        current_password_input.focus()
        weak_badge = PasswordBadge(browser)
        assert weak_badge.get_text() == language.tr('PASSWORD_WEAK_BADGE')
        weak_badge.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_WEAK_TOOLTIP')
        assert new_password_input.is_encircled_by(ERROR_RED)
        uppercase_password = "UPPERCASE"
        new_password_input.set_password(uppercase_password)
        current_password_input.focus()
        weak_badge_2 = PasswordBadge(browser)
        assert weak_badge_2.get_text() == language.tr('PASSWORD_WEAK_BADGE')
        weak_badge_2.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_WEAK_TOOLTIP')
        assert new_password_input.is_encircled_by(ERROR_RED)
        numbers_password = "1234567890"
        new_password_input.set_password(numbers_password)
        current_password_input.focus()
        weak_badge_3 = PasswordBadge(browser)
        assert weak_badge_3.get_text() == language.tr('PASSWORD_WEAK_BADGE')
        weak_badge_3.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_WEAK_TOOLTIP')
        assert new_password_input.is_encircled_by(ERROR_RED)
        symbol_password = '!@#$%^&*()_-+='
        new_password_input.set_password(symbol_password)
        current_password_input.focus()
        weak_badge_4 = PasswordBadge(browser)
        assert weak_badge_4.get_text() == language.tr('PASSWORD_WEAK_BADGE')
        weak_badge_4.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_WEAK_TOOLTIP')
        assert new_password_input.is_encircled_by(ERROR_RED)
        lower_upper_password = "lowerUPPER"
        new_password_input.set_password(lower_upper_password)
        current_password_input.focus()
        fair_badge = PasswordBadge(browser)
        assert fair_badge.get_text() == language.tr('PASSWORD_FAIR_BADGE')
        fair_badge.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_WEAK_TOOLTIP')
        lower_number_password = "lower1234567890"
        new_password_input.set_password(lower_number_password)
        current_password_input.focus()
        fair_badge_2 = PasswordBadge(browser)
        assert fair_badge_2.get_text() == language.tr('PASSWORD_FAIR_BADGE')
        fair_badge_2.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_WEAK_TOOLTIP')
        lower_symbol_password = "lower!@#$%^&*()_-+="
        new_password_input.set_password(lower_symbol_password)
        current_password_input.focus()
        fair_badge_3 = PasswordBadge(browser)
        assert fair_badge_3.get_text() == language.tr('PASSWORD_FAIR_BADGE')
        fair_badge_3.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_WEAK_TOOLTIP')
        upper_number_password = "UPPER1234567890"
        new_password_input.set_password(upper_number_password)
        current_password_input.focus()
        fair_badge_4 = PasswordBadge(browser)
        assert fair_badge_4.get_text() == language.tr('PASSWORD_FAIR_BADGE')
        fair_badge_4.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_WEAK_TOOLTIP')
        upper_symbol_password = "UPPER!@#$%^&*()_-+="
        new_password_input.set_password(upper_symbol_password)
        current_password_input.focus()
        fair_badge_5 = PasswordBadge(browser)
        assert fair_badge_5.get_text() == language.tr('PASSWORD_FAIR_BADGE')
        fair_badge_5.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_WEAK_TOOLTIP')
        number_symbol = "1234567890!@#$%^&*()_-+="
        new_password_input.set_password(number_symbol)
        current_password_input.focus()
        fair_badge_6 = PasswordBadge(browser)
        assert fair_badge_6.get_text() == language.tr('PASSWORD_FAIR_BADGE')
        fair_badge_6.hover_over()
        assert PasswordTooltip(browser).get_text() == language.tr('PASSWORD_WEAK_TOOLTIP')
        lower_upper_number_password = "lowerUPPER1234567890"
        new_password_input.set_password(lower_upper_number_password)
        current_password_input.focus()
        assert PasswordBadge(browser).get_text() == language.tr('PASSWORD_GOOD_BADGE')
        lower_upper_symbol_password = "lowerUPPER!@#$%^&*()_-+="
        new_password_input.set_password(lower_upper_symbol_password)
        current_password_input.focus()
        assert PasswordBadge(browser).get_text() == language.tr('PASSWORD_GOOD_BADGE')
        lower_number_symbol_password = "lower1234567890!@#$%^&*()_-+="
        new_password_input.set_password(lower_number_symbol_password)
        current_password_input.focus()
        assert PasswordBadge(browser).get_text() == language.tr('PASSWORD_GOOD_BADGE')
        upper_number_symbol_password = "UPPER1234567890!@#$%^&*()_-+="
        new_password_input.set_password(upper_number_symbol_password)
        current_password_input.focus()
        assert PasswordBadge(browser).get_text() == language.tr('PASSWORD_GOOD_BADGE')


if __name__ == '__main__':
    exit(test_invalid_new_passwords().main())
