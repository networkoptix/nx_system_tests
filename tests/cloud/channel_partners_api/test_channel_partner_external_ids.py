# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time

from cloud_api.cloud import assert_channel_partners_supported
from cloud_api.cloud import make_cloud_account_factory
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest


class test_channel_partner_external_ids(CloudTest):
    """Test Channel Partner External IDs requests.

    Selection-Tag: channel_partners_api
    Selection-Tag: cloud_portal_gitlab
    Selection-Tag: cloud_portal_smoke
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        assert_channel_partners_supported(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cp_data = cloud_account_factory.grant_channel_partner_access()
        [root_cp_id, _root_cp_admin] = cloud_account_factory.prepare_root_cp_with_admin(cp_data)
        [sub_cp_id, sub_cp_admin] = cloud_account_factory.prepare_sub_cp_with_admin(cp_data)
        sub_admin_cp_api = sub_cp_admin.make_channel_partner_api()
        assert not sub_admin_cp_api.list_external_ids(sub_cp_id)
        unique_external_id = f'external_id_{int(time.perf_counter_ns())}'
        sub_admin_cp_api.set_external_id(unique_external_id, root_cp_id, sub_cp_id)
        [new_id] = sub_admin_cp_api.list_external_ids(sub_cp_id)
        assert new_id.get_custom_id() == unique_external_id, (
            f"{new_id.get_custom_id()} != {unique_external_id}")
        assert new_id.get_channel_partner_uuid() == root_cp_id, (
            f"{new_id.get_channel_partner_uuid()} != {root_cp_id}")
        assert new_id.get_full_id() == f"{sub_cp_id}--{unique_external_id}", (
            f"{new_id.get_full_id()} != {sub_cp_id}--{unique_external_id}")
        id_details = sub_admin_cp_api.get_external_id_details(unique_external_id, sub_cp_id)
        assert id_details.get_custom_id() == unique_external_id, (
            f"{id_details.get_custom_id()} != {unique_external_id}")
        assert id_details.get_channel_partner_uuid() == root_cp_id, (
            f"{id_details.get_channel_partner_uuid()} != {root_cp_id}")
        assert id_details.get_full_id() == f"{sub_cp_id}--{unique_external_id}", (
            f"{id_details.get_full_id()} != {sub_cp_id}--{unique_external_id}")
        firstly_updated_external_id = f'new_external_id_{int(time.perf_counter_ns())}'
        sub_admin_cp_api.update_external_id_fully(
            old_external_id=unique_external_id,
            cp_id=sub_cp_id,
            new_external_id=firstly_updated_external_id,
            target_cp_id=root_cp_id,
            )
        assert sub_admin_cp_api.get_external_id_details(unique_external_id, sub_cp_id) is None
        new_details = sub_admin_cp_api.get_external_id_details(firstly_updated_external_id, sub_cp_id)
        assert new_details.get_custom_id() == firstly_updated_external_id, (
            f"{new_details.get_custom_id()} != {firstly_updated_external_id}")
        assert new_details.get_channel_partner_uuid() == root_cp_id, (
            f"{new_details.get_channel_partner_uuid()} != {root_cp_id}")
        assert new_details.get_full_id() == f"{sub_cp_id}--{firstly_updated_external_id}", (
            f"{new_details.get_full_id()} != {sub_cp_id}--{firstly_updated_external_id}")
        secondly_updated_external_id = f'new_external_id_{int(time.perf_counter_ns())}'
        sub_admin_cp_api.patch_external_id_name(
            old_external_id=firstly_updated_external_id,
            new_external_id=secondly_updated_external_id,
            cp_id=sub_cp_id,
            )
        new_details = sub_admin_cp_api.get_external_id_details(secondly_updated_external_id, sub_cp_id)
        assert new_details.get_custom_id() == secondly_updated_external_id, (
            f"{new_details.get_custom_id()} != {secondly_updated_external_id}")
        assert new_details.get_channel_partner_uuid() == root_cp_id, (
            f"{new_details.get_channel_partner_uuid()} != {root_cp_id}")
        assert new_details.get_full_id() == f"{sub_cp_id}--{secondly_updated_external_id}", (
            f"{new_details.get_full_id()} != {sub_cp_id}--{firstly_updated_external_id}")
        sub_admin_cp_api.delete_external_id(secondly_updated_external_id, sub_cp_id)
        assert not sub_admin_cp_api.list_external_ids(sub_cp_id)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_channel_partner_external_ids()]))
