# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.metadata_api.test_metadata_api__ import _test_metadata_api
from tests.base_test import VMSTest


class test_ubuntu22_v4(VMSTest):
    """Test metadata api.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_metadata_api(args.distrib_url, 'ubuntu22', 'v4', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4().main())
