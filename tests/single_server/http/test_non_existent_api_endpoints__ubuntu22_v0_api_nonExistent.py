# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.http.test_non_existent_api_endpoints__ import _test_non_existent_api_endpoints


class test_ubuntu22_v0_api_nonExistent(VMSTest):
    """Test non existent api endpoints.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_non_existent_api_endpoints(args.distrib_url, 'ubuntu22', '/api/nonExistent', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_api_nonExistent().main())
