# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from doubles import licensing
from runner.ft_test import FTTest
from runner.ft_test import run_ft_test


class test_generate_license(FTTest):
    """Test generate license.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        license_server = licensing.get_remote_licensing_server()
        license_key = license_server.generate({'BRAND2': 'hdwitness'})
        response = license_server.info(license_key)
        assert response['body']['key'] == license_key
        assert response['body']['is_enabled']


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [
        test_generate_license(),
        ]))
