# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import unittest
from pathlib import Path

from mediaserver_api import Diff
from mediaserver_api import full_info_differ
from mediaserver_api import transaction_log_differ


class DataDifferOnRealFilesTest(unittest.TestCase):

    def test(self):
        my_path = Path(__file__)
        files_dir = my_path.with_name(my_path.stem + '_files')
        for differ in [full_info_differ, transaction_log_differ]:
            for diff_path in files_dir.glob('{}-*-diff.txt'.format(differ.name)):
                base_name = diff_path.stem.rsplit('-', 1)[0]
                file_stem = base_name[len(differ.name) + 1:]
                with self.subTest(differ=differ.name, file=file_stem):
                    base_name = differ.name + '-' + file_stem
                    x = json.loads(files_dir.joinpath(base_name + '-x').with_suffix('.json').read_text())
                    y = json.loads(files_dir.joinpath(base_name + '-y').with_suffix('.json').read_text())
                    diff_list_text = files_dir.joinpath(base_name + '-diff').with_suffix('.txt').read_text()
                    expected_diff_list = []
                    for line in diff_list_text.rstrip().splitlines():
                        path_str, element_name, action, x1, y1 = line.split()
                        path = [] if path_str == '/' else path_str.strip('/').split('/')
                        expected_diff_list.append(Diff(path, element_name, action, json.loads(x1), json.loads(y1)))
                    diff_list = differ.diff(x, y)
                    self.assertSetEqual(set(diff_list), set(expected_diff_list))
