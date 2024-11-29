# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Mapping


class TranslationTable:

    def __init__(self, language_code: str, text_mapping: Mapping[str, str]):
        self._code = language_code
        self._text_mapping = text_mapping

    def code(self) -> str:
        return self._code

    def tr(self, text: str) -> str:
        try:
            return self._text_mapping[text]
        except KeyError:
            raise RuntimeError(f"Translation for {text!r} is not found for language {self._code}")

    def __repr__(self):
        entry_count = len(self._text_mapping)
        return f'<{self.__class__.__name__}: code={self._code} entry_count={entry_count}>'


en_us = TranslationTable("en_US", {
    "ACCEPT": "Accept",
    "ACCEPT_RISK_TEXT": "Accept the risks and continue",
    "ACCOUNT_ACTIVATED": "Account Activated!",
    "ACCOUNT_CREATED": "Account Created!",
    "ACCOUNT_SAVED": "Your account is successfully saved",
    "ADVANCED_SEARCH_BUTTON_TEXT": "Advanced Search",
    "BETAS": "Betas",
    "BUG_FIXES": "BUG FIXES",
    "CANCEL_1": "CANCEL",
    "CANCEL_2": "Cancel",
    "CREATE_ACCOUNT": "CREATE ACCOUNT",
    "CREATE_ACCOUNT_BUTTON_TEXT": "Create Account",
    "DEVICES": "devices",
    "CONNECT": "Connect",
    "CONNECT_SYSTEM_TO": "Connect system to",
    "DISABLED": "DISABLED",
    "DISABLE": "Disable",
    "DISCONNECT_FROM_MY_ACCOUNT": "Disconnect from My Account",
    "DISCONNECT_MODAL_WARNING": "You will not be able to access this System anymore.",
    "DISCONNECT": "Disconnect",
    "DOWNLOADS": "Downloads",
    "DOWNLOAD": "Download",
    "DOWNLOAD_LINKS": "Download Links",
    "ENABLED": "ENABLED",
    "ENABLE_2FA": "Enable 2FA",
    "FORGOT_PASSWORD": "Forgot Password?",
    "LAST_DAY": "Last Day",
    "LAST_SEVEN_DAYS": "Last 7 Days",
    "LAST_THIRTY_DAYS": "Last 30 Days",
    "IMPROVEMENTS": "IMPROVEMENTS",
    "LOG_IN": "Log In",
    "MANUFACTURERS": "manufacturers",
    "NEXT": "Next",
    "NO_UNSAVED_CHANGES": "No unsaved changes",
    "OFFLINE_BADGE": "offline",
    "OPEN_SOURCE_SOFTWARE_DISCLOSURE": "OPEN SOURCE SOFTWARE DISCLOSURE",
    "OWNERSHIP_TRANSFER_START": "You are about to transfer ownership to",
    "OWNERSHIP_TRANSFER_WARNING": "Once the ownership transfer is complete, you will be removed from the system",
    "PASSWORD_SUCCESSFULLY_CHANGED": "Password successfully changed",
    "PASSWORD_TOO_SHORT_BADGE": "TOO SHORT",
    "PASSWORD_TOO_SHORT_TOOLTIP": "Password must contain at least 8 characters",
    "PASSWORD_INCORRECT_BADGE": "INCORRECT",
    "PASSWORD_SPECIAL_CHARS":
        "Use only latin letters, numbers and keyboard symbols, avoid leading and trailing spaces",
    "PASSWORD_WEAK_BADGE": "WEAK",
    "PASSWORD_WEAK_TOOLTIP": (
        "Use numbers, upper and lower case letters and special "
        "characters to make your password stronger"),
    "PASSWORD_FAIR_BADGE": "FAIR",
    "PASSWORD_GOOD_BADGE": "GOOD",
    "PASSWORD_IS_SET": "Password is set!",
    "PATCHES": "Patches",
    "PRIVACY": "Privacy",
    "RELEASES": "Releases",
    "RELEASE_NOTES": "Release Notes",
    "REQUEST_SENT": "Request has been sent",
    "RESET_PASSWORD": "Reset Password",
    "RESET_PASSWORD_EMAIL_SUBJECT": "Reset your password",
    "SAVE": "SAVE",
    "SAVE_2": "Save",
    "SERVICES": "Services",
    "SET_NEW_PASSWORD": "Set New Password",
    "SUBMIT_A_REQUEST": "submit a request",
    "SUPPORT": "Support",
    "SUPPORTED_DEVICES_TAB": "Supported Devices",
    "SYSTEMS_ENTRY_IN_HEADER_NAV": "systems",
    "SYSTEM_CALCULATOR": "System Calculator",
    "SYSTEM_DISCONNECTED_TOAST_TEXT": "System is successfully disconnected from %CLOUD_NAME%",
    "SYSTEM_IS_OFFLINE_TEXT": "System is offline. Some settings may not be available.",
    "SYSTEM_2FA_ENABLED": "Two-factor authentication will now be forced for this system",
    "SYSTEMS_LABEL": "Systems",
    "TERMS_AND_CONDITIONS": "Terms and conditions",
    "TERMS": "Terms",
    "NO_ACCESS_TO_AUTH_APP": "No access to authentication app?",
    "VIDEO_FORMAT_ERROR": "The video format for this bookmark is not supported by your browser. Please download it to view locally",
    "VIEW_FULL_RECORDING": "View Full Recording",
    "WRONG_BACKUP_CODE": "Wrong Backup Code",
    "YOU_HAVE_NO_SYSTEMS_TEXT": "You have no Systems",
    })

de_de = TranslationTable("de_DE", {
    "ACCOUNT_SAVED": "Ihr Account wurde erfolgreich gespeichert",
    "CANCEL_2": "Abbrechen",
    "SAVE_2": "Speichern",
    })
