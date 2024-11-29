# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from directories._cleanup import OldestFilesFirst
from directories._directories import CannotDeleteEntry


class TestEntries(unittest.TestCase):

    def setUp(self):
        self._tempdir = TemporaryDirectory()
        self._root = Path(self._tempdir.name)
        self._entry_root = OldestFilesFirst([self._root])
        self._root_files = [
            self._mkfile('1.txt'),
            self._mkfile('2.txt'),
            self._mkfile('3.txt'),
            self._mkfile('4.txt'),
            self._mkfile('5.txt'),
            self._mkfile('6.txt'),
            ]
        self._nested_directories = [
            self._mkdir('one'),
            self._mkfile('one/1.txt'),
            self._mkfile('one/2.txt'),
            self._mkfile('one/3.txt'),
            self._mkdir('two'),
            self._mkfile('two/1.txt'),
            self._mkfile('two/2.txt'),
            self._mkfile('two/3.txt'),
            self._mkdir('three'),
            self._mkfile('three/1.txt'),
            self._mkfile('three/2.txt'),
            self._mkfile('three/3.txt'),
            ]
        self._non_empty_dir = [
            self._mkdir('dir'),
            self._mkfile('dir/file.txt'),
            ]
        self._all_files = [
            *self._root_files,
            *self._nested_directories,
            *self._non_empty_dir,
            ]
        self.maxDiff = 2000

    def tearDown(self):
        self._tempdir.cleanup()

    def test_file_order_on_write(self):
        # Check only file order as directory mtime can change unpredictably on file writes.
        self.assertListEqual(
            [e.path() for e in self._entry_root.list_entries() if e.path().is_file()],
            [p for p in self._all_files if p.is_file()])

    def test_list_multiple_roots(self):
        nested_root = OldestFilesFirst([self._root / 'one', self._root / 'two', self._root / 'three'])
        self.assertListEqual(
            [e.path() for e in nested_root.list_entries()],
            [p for p in self._nested_directories if p.is_file()])

    def test_file_order_on_read(self):
        [first_file, *_] = self._root_files
        _read_file_to_change_atime(first_file)
        [*_, latest_entry] = self._entry_root.list_entries()
        self.assertEqual(latest_entry.path(), first_file)

    def test_file_order_on_touch(self):
        [first_file, *_] = self._root_files
        _touch_file_to_change_mtime(first_file)
        [*_, latest_entry] = self._entry_root.list_entries()
        self.assertEqual(latest_entry.path(), first_file)

    def test_delete_directory(self):
        [directory, file_in_directory] = self._non_empty_dir
        entries = self._entry_root.list_entries()
        [dir_entry] = [e for e in entries if e.path() == directory]
        [file_entry] = [e for e in entries if e.path() == file_in_directory]
        self.assertRaises(CannotDeleteEntry, dir_entry.delete)
        self.assertTrue(dir_entry.path().exists())
        file_entry.delete()
        self.assertFalse(file_entry.path().exists())
        dir_entry.delete()
        self.assertFalse(dir_entry.path().exists())

    def _mkdir(self, relative_path):
        d = self._root / relative_path
        d.mkdir()
        time.sleep(0.01)  # Sleep so directories have different mtime.
        return d

    def _mkfile(self, relative_path):
        f = self._root / relative_path
        f.write_bytes(b'a' * 10)
        time.sleep(0.01)  # Sleep so files have different mtime.
        return f


def _touch_file_to_change_mtime(path: Path):
    started_at = time.monotonic()
    stat_before_read = path.stat()
    while True:
        path.touch()
        if path.stat().st_mtime != stat_before_read.st_mtime:
            break
        time.sleep(0.05)
        if time.monotonic() - started_at > 1:
            raise RuntimeError("File st_time did not change on touch")


def _read_file_to_change_atime(path: Path):
    started_at = time.monotonic()
    stat_before_read = path.stat()
    while True:
        path.read_text()
        if path.stat().st_atime != stat_before_read.st_atime:
            break
        time.sleep(0.05)
        if time.monotonic() - started_at > 1:
            raise RuntimeError("File st_time did not change on touch")
