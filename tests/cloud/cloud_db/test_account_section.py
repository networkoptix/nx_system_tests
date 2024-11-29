# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time

from cloud_api._imap import IMAPConnection
from cloud_api.cloud import make_cloud_account_factory
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest


class test_account(CloudTest):
    """Test account-related requests.

    Selection-Tag: cloud_db
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        account = cloud_account_factory.create_unregistered_account()
        assert not account.user_is_accessible()
        account.register_user_cdb()
        actual_status_code = account.get_status_code()
        expected_status_code = "awaitingEmailConfirmation"
        assert actual_status_code == expected_status_code, (
            f"{actual_status_code} != {expected_status_code}")
        code = account.get_activation_code()
        account.activate_user(code)
        assert account.user_is_accessible()
        actual_status_code = account.get_status_code()
        expected_status_code = "activated"
        assert actual_status_code == expected_status_code, (
            f"{actual_status_code} != {expected_status_code}")
        new_name = f'New Name User {time.perf_counter_ns()}'
        account.rename_user(new_name)
        updated_user_info = account.get_user_info()
        updated_full_name = updated_user_info.get_full_name()
        assert updated_full_name == new_name, f"{updated_full_name} != {new_name}"
        assert account.get_self_info().get_raw_data() == updated_user_info.get_raw_data()
        actual_security_settings = account.get_security_settings()
        assert actual_security_settings['httpDigestAuthEnabled']
        assert not actual_security_settings['account2faEnabled']
        assert not actual_security_settings['totpExistsForAccount']
        [temp_login, temp_password] = account.get_temporary_credentials()
        user_info_temp_credentials = account.get_user_info_request_with_credentials(
            temp_login,
            temp_password,
            )
        assert user_info_temp_credentials == updated_user_info.get_raw_data()
        assert updated_user_info.get_raw_data() == account.get_user_info().get_raw_data()
        account.request_password_reset()
        with IMAPConnection(*cloud_account_factory.get_imap_credentials()) as imap_connection:
            subject = "Reset your password"
            message_id = imap_connection.get_message_id_by_subject(account.user_email, subject)
            imap_connection.get_restore_password_link(message_id)
        assert account.user_is_accessible()
        account.delete_user()
        assert not account.user_is_accessible()


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_account()]))
