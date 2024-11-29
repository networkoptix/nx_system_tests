# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.html_elements import Button
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement


class LoginForm:

    def __init__(self, browser: Browser):
        self._browser = browser

    def incorrect_password_badge(self) -> WebDriverElement:
        incorrect_password_xpath = (
            "//nx-login-webadmin-modal//div[contains(text(), 'Wrong login or password')]"
            )
        return self._browser.wait_element(ByXPATH(incorrect_password_xpath), 10)

    def get_login_field(self) -> InputField:
        email_xpath = "//nx-login-webadmin-modal//input[@id='login_email']"
        return InputField(self._browser.wait_element(ByXPATH(email_xpath), 10))

    def get_password_field(self) -> InputField:
        password_xpath = "//nx-login-webadmin-modal//input[@id='login_password']"
        return InputField(self._browser.wait_element(ByXPATH(password_xpath), 10))

    def get_submit_button(self) -> Button:
        submit_xpath = "//nx-login-webadmin-modal//button[@type='submit']"
        return Button(self._browser.wait_element(ByXPATH(submit_xpath), 10))
