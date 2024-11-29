# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api._cloud import BatchRequestFailed
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Groups
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.infra import assert_raises
from vm.networks import setup_flat_network


class test_system_users(VMSTest, CloudTest):
    """Test system-related requests.

    Selection-Tag: cloud_db
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        cloud_owner = cloud_account_factory.create_account()
        distrib = installer_supplier.distrib()
        customization_name = distrib.customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        server = stand.mediaserver()
        server.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses],
            )
        server.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        server.set_cloud_host(cloud_host)
        server.start()
        server.api.setup_cloud_system(cloud_owner)
        system_id = server.api.get_cloud_system_id()
        cloud_users_emails = []
        cloud_users_emails.append(cloud_owner.user_email)
        first_cloud_user = cloud_account_factory.create_account()
        server.api.add_cloud_user(
            name=first_cloud_user.user_email,
            email=first_cloud_user.user_email,
            permissions=[Permissions.ADMIN],
            )
        cloud_users_emails.append(first_cloud_user.user_email)
        second_cloud_user = cloud_account_factory.create_account()
        server.api.add_cloud_user(
            name=second_cloud_user.user_email,
            email=second_cloud_user.user_email,
            permissions=[Permissions.ADMIN],
            )
        cloud_users_emails.append(second_cloud_user.user_email)
        third_cloud_user = cloud_account_factory.create_account()
        server.api.add_cloud_user(
            name=third_cloud_user.user_email,
            email=third_cloud_user.user_email,
            permissions=[Permissions.ADMIN],
            )
        cloud_users_emails.append(third_cloud_user.user_email)
        system_users_emails = [
            user.get_email() for user in cloud_owner.list_system_users(system_id)]
        assert sorted(system_users_emails) == sorted(cloud_users_emails)
        new_user = cloud_account_factory.create_account()
        cloud_owner.share_system(system_id, new_user.user_email, user_groups=[Groups.VIEWERS])
        # TODO: Uncomment when IMAP service is stabilized.
        # See: https://networkoptix.atlassian.net/browse/ITSUPPORT-224
        # with IMAPConnection(*cloud_account_factory.get_imap_credentials()) as imap_connection:
        #     subject = f"Video system {server.api.get_system_name()} was shared with you"
        #     message_id = imap_connection.get_message_id_by_subject(new_user.user_email, subject)
        #     assert imap_connection.has_link_to_cloud_instance_in_message(message_id, cloud_host)
        #     link_to_system_page = imap_connection.get_link_to_cloud_system(message_id)
        # browser = exit_stack.enter_context(browser_stand.browser())
        # browser.open(link_to_system_page)
        # LoginComponent(browser).login(new_user.user_email, new_user.password)
        # updated_system_users_emails = [
        #     user.get_email() for user in cloud_owner.list_system_users(system_id)]
        # assert new_user.user_email in updated_system_users_emails
        cloud_owner.stop_sharing_system(system_id, third_cloud_user.user_email)
        current_users = [user.get_email() for user in cloud_owner.list_system_users(system_id)]
        assert third_cloud_user.user_email not in current_users
        assert not cloud_owner.list_system_user_attributes(system_id)
        first_attribute_name = 'first_name'
        first_attribute_value = 'first_value'
        second_attribute_name = 'second_name'
        second_attribute_value = 'second_value'
        first_added_attribute = {'name': first_attribute_name, 'value': first_attribute_value}
        second_added_attribute = {'name': second_attribute_name, 'value': second_attribute_value}
        cloud_owner.add_system_user_attributes(system_id, [
            first_added_attribute,
            second_added_attribute,
            ])
        received_attributes = cloud_owner.list_system_user_attributes(system_id)
        assert first_added_attribute in received_attributes, (
            f'Attribute {first_added_attribute} not found '
            f'among received attributes {received_attributes}')
        assert second_added_attribute in received_attributes
        updated_value = 'updated_value'
        cloud_owner.update_system_user_attribute(system_id, second_attribute_name, updated_value)
        received_attributes = cloud_owner.list_system_user_attributes(system_id)
        assert {'name': second_attribute_name, 'value': updated_value} in received_attributes
        cloud_owner.delete_system_user_attribute(system_id, second_attribute_name)
        received_attributes = cloud_owner.list_system_user_attributes(system_id)
        assert not {'name': second_attribute_name, 'value': updated_value} in received_attributes
        assert len(received_attributes) == 1
        out_of_system_user = cloud_account_factory.create_unregistered_account()
        cloud_owner.create_batch(
            system_ids=[system_id],
            user_emails=[
                first_cloud_user.user_email,
                second_cloud_user.user_email,
                out_of_system_user.user_email,
                ],
            role_ids=[Groups.VIEWERS],
            attributes={"additionalBatchAttr": "BatchTestValue"},
            )
        viewer_role_name = 'viewer'
        new_power_user = cloud_owner.get_system_user_by_email(
            system_id,
            first_cloud_user.user_email,
            )
        new_power_user_role = new_power_user.get_role()
        new_advanced_viewer_user = cloud_owner.get_system_user_by_email(
            system_id,
            second_cloud_user.user_email,
            )
        new_advanced_viewer_user_role = new_advanced_viewer_user.get_role()
        assert new_power_user_role == viewer_role_name, (
            f"{new_power_user_role} != {viewer_role_name}")
        assert new_advanced_viewer_user_role == viewer_role_name, (
                f"{new_advanced_viewer_user_role} != {viewer_role_name}")
        actual_system_users = [
            user.get_email() for user in cloud_owner.list_system_users(system_id)]
        assert out_of_system_user.user_email in actual_system_users, (
            f"User email {out_of_system_user.user_email} not found among {actual_system_users}")
        not_email_input = str(cloud_owner.get_user_info().get_id())
        with assert_raises(BatchRequestFailed) as e:
            cloud_owner.create_batch(
                system_ids=[system_id],
                user_emails=[not_email_input],
                role_ids=[Groups.VIEWERS],
                attributes={"additionalBatchAttr": "BatchTestValue"},
                )
            assert "is not a valid email address" in str(e), (
                f"Actual error description: {str(e)}")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_system_users()]))
