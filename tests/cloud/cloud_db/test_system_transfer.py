# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time
from ipaddress import IPv4Network
from uuid import UUID

from cloud_api import CloudAccount
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from vm.networks import setup_flat_network


class test_system_transfer(VMSTest, CloudTest):
    """Test requests related to system transfer.

    Selection-Tag: cloud_db
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        initial_cloud_owner = cloud_account_factory.create_account()
        new_account_owner = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        initial_cloud_owner.set_user_customization(customization_name)
        services_hosts = initial_cloud_owner.get_services_hosts()
        setup_flat_network([stand.vm()], IPv4Network('10.254.10.0/28'))
        mediaserver = stand.mediaserver()
        mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.setup_cloud_system(initial_cloud_owner)
        mediaserver.api.add_cloud_user(
            name=new_account_owner.user_email,
            email=new_account_owner.user_email,
            permissions=Permissions.VIEWER_PRESET,
            )
        system_id = mediaserver.api.get_cloud_system_id()
        _wait_for_user_in_the_system(initial_cloud_owner, system_id, new_account_owner.user_email)
        comment_text = "Gift"
        initial_cloud_owner.offer_system(
            system_id,
            new_account_owner.user_email,
            comment=comment_text,
            )
        [offer] = initial_cloud_owner.list_system_offers()
        assert offer.from_account() == initial_cloud_owner.user_email
        assert offer.to_account() == new_account_owner.user_email
        assert offer.system_id() == system_id
        assert offer.comment() == comment_text
        assert offer.status() == 'offered'
        initial_cloud_owner.revoke_system_offer(system_id)
        assert not initial_cloud_owner.list_system_offers()
        comment_text = "Second_gift"
        initial_cloud_owner.offer_system(
            system_id,
            new_account_owner.user_email,
            comment=comment_text,
            )
        [offer] = initial_cloud_owner.list_system_offers()
        assert offer.comment() == comment_text
        new_account_owner.reject_system_offer(system_id)
        assert not initial_cloud_owner.list_system_offers()
        comment_text = "Third_gift"
        initial_cloud_owner.offer_system(
            system_id,
            new_account_owner.user_email,
            comment=comment_text,
            )
        new_account_owner.accept_system_offer(system_id)
        [user] = new_account_owner.list_system_users(system_id)
        assert user.get_email() == new_account_owner.user_email
        assert user.get_role() == 'owner'
        assert not initial_cloud_owner.can_access_system(system_id)
        assert not new_account_owner.list_system_offers()


def _wait_for_user_in_the_system(
        cloud_owner: CloudAccount,
        system_id: UUID,
        target_user_email: str,
        ):
    started_at = time.monotonic()
    timeout = 5
    while True:
        users = cloud_owner.list_system_users(system_id)
        for user in users:
            if user.get_email() == target_user_email:
                return
        if time.monotonic() - started_at > timeout:
            raise RuntimeError(f"No user {target_user_email} in the system")
        time.sleep(1)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_system_transfer()]))
