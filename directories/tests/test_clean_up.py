# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import itertools
import logging
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Collection

from directories._cleanup import GradualCleanup
from directories._cleanup import OldestFilesFirst


class TestNoCleanup(unittest.TestCase):

    def setUp(self):
        self._tempdir = TemporaryDirectory()
        self._root = Path(self._tempdir.name)
        self._directory_collection = _DirectoryCollection([self._root])
        self.maxDiff = 2000

    def tearDown(self):
        self._tempdir.cleanup()

    def test_no_cleanup_without_new_files(self):
        self._directory_collection.add_entries()
        entry_root = self._directory_collection.entry_root()
        initial_entries = entry_root.list_entries()
        time.sleep(0.01)  # Sleep so cleanup time is greater than file usage time.
        strategy = GradualCleanup(
            target_size=0, last_cleanup_at=time.time(), entry_root=entry_root)
        strategy.delete_least_significant()
        # If nothing was created since last cleanup - nothing should be deleted.
        self.assertSequenceEqual(entry_root.list_entries(), initial_entries)
        # Files that was not modified should not be treated as newly created.
        self._directory_collection.change_files_atime()
        strategy.delete_least_significant()
        self.assertSequenceEqual(entry_root.list_entries(), initial_entries)

    def test_no_cleanup_below_target_size(self):
        entry_root = self._directory_collection.entry_root()
        strategy = GradualCleanup(
            target_size=1024 * 1024 * 1024,  # Arbitrary big.
            last_cleanup_at=0,
            entry_root=entry_root,
            )
        entries = []
        entries.extend(self._directory_collection.add_entries())
        strategy.delete_least_significant()
        self.assertSequenceEqual(entry_root.list_entries(), entries)
        entries.extend(self._directory_collection.add_entries())
        strategy.delete_least_significant()
        self.assertSequenceEqual(entry_root.list_entries(), entries)
        entries.extend(self._directory_collection.add_entries())
        strategy.delete_least_significant()
        self.assertSequenceEqual(entry_root.list_entries(), entries)


class TestCleanup(unittest.TestCase):

    def setUp(self):
        self._tempdir = TemporaryDirectory()
        self._root = Path(self._tempdir.name)
        directories = [self._root / f'dir_{i}' for i in range(5)]
        for directory in directories:
            directory.mkdir()
        self._directory_collection = _DirectoryCollection(directories)
        # Create initial files.
        for _ in range(5):
            self._directory_collection.add_entries()
        if not self._directory_collection.entry_root().list_entries():
            raise RuntimeError('Failed to create initial files')

    def tearDown(self):
        self._tempdir.cleanup()

    def test_maintain_target_size_and_file_rotation(self):
        initial_entries = self._directory_collection.entry_root().list_entries()
        entry_root = self._directory_collection.entry_root()
        target_size = entry_root.total_size()
        for _ in range(6):
            last_cleanup_at = entry_root.list_entries()[-1].used_at() + 0.001
            time.sleep(0.01)  # Sleep so file usage time is greater than last cleanup time.
            new_entries = self._directory_collection.add_entries()
            strategy = GradualCleanup(target_size, last_cleanup_at, entry_root)
            strategy.delete_least_significant()
            self.assertLessEqual(entry_root.total_size(), target_size)
            self.assertTrue(all(e in entry_root.list_entries() for e in new_entries))
        self.assertFalse(any(e in entry_root.list_entries() for e in initial_entries))

    def test_gradual_cleanup_with_small_target_size(self):
        entry_root = self._directory_collection.entry_root()
        cleanup_count = 0
        while True:
            last_cleanup_at = entry_root.list_entries()[-1].used_at() + 0.001
            time.sleep(0.01)  # Sleep so file usage time is greater than last cleanup time.
            self._directory_collection.add_entries()  # Clean up will not work without new files.
            strategy = GradualCleanup(
                target_size=0, last_cleanup_at=last_cleanup_at, entry_root=entry_root)
            total_size_before_cleanup = entry_root.total_size()
            strategy.delete_least_significant()
            cleanup_count += 1
            self.assertLessEqual(entry_root.total_size(), total_size_before_cleanup)
            if entry_root.total_size() == 0:
                self.assertGreater(cleanup_count, 1)
                break
            if cleanup_count > 10:
                raise RuntimeError("Directories are not empty after 10 cleanups")


class _DirectoryCollection:

    def __init__(self, directories: Collection[Path]):
        self._directories = directories
        self._entry_root = OldestFilesFirst(directories)
        self._file_size = 1024
        self._file_index = itertools.count(1)

    def list_entries(self):
        return self._entry_root.list_entries()

    def add_entries(self):
        created_files = []
        base_time = time.time()
        for directory in self._directories:
            for _ in range(5):
                file_index = next(self._file_index)
                created_files.append(directory / f'file_{file_index:04d}.txt')
                created_files[-1].write_bytes(b'a' * self._file_size)
                # Set different atime and mtime for each file.
                # Faster and more precise than time.sleep().
                os.utime(created_files[-1], (base_time + 0.001 * file_index, base_time + 0.001 * file_index))
        return [e for e in self._entry_root.list_entries() if e.path() in created_files]

    def change_files_atime(self):
        entries = self.list_entries()
        current_time = time.time()
        for i, e in enumerate(entries, 1):
            mtime = e.used_at()
            atime = current_time + 0.001 * i  # Preserve file order.
            os.utime(e.path(), (atime, mtime))

    def entry_root(self):
        return self._entry_root


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
