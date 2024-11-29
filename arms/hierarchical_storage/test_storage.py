# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import subprocess
import tempfile
import unittest
from pathlib import Path

from arms.hierarchical_storage.storage import ChildExists
from arms.hierarchical_storage.storage import ChildNotExist
from arms.hierarchical_storage.storage import PendingSnapshot
from arms.hierarchical_storage.storage import QCOWRootDisk
from arms.hierarchical_storage.storage import SnapshotAlreadyPending


def _qemu_img(*args: str):
    command = ['qemu-img', *args]
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as err:
        logging.error("Error at executing '%s'", ' '.join(command))
        raise RuntimeError(f"QEMU error: {err.stderr}")


def _create_raw_disk(path: Path, size_mb: int):
    logging.info("Creating raw disk %s with size %s Mb ...", path, size_mb)
    filler = bytes(range(256))
    filler_length = len(filler)
    written_bytes = 0
    size_bytes = size_mb * 1024 * 1024
    with path.open('wb') as fd:
        while True:
            to_write = min(filler_length, size_bytes - written_bytes)
            if to_write <= 0:
                return
            fd.write(filler[:to_write])
            written_bytes += to_write


def _raw_to_qcow2(raw: Path, qcow2: Path):
    logging.info("Converting %s => %s ...", raw, qcow2)
    _qemu_img('convert', '-f', 'raw', '-O', 'qcow2', str(raw), str(qcow2))


def _create_qcow_disk(qcow2_path: Path, size_mb: int):
    if qcow2_path.suffix != '.qcow2':
        raise RuntimeError(f"{qcow2_path} is not QCOW2 file")
    raw_path = qcow2_path.with_name(qcow2_path.stem + '.raw')
    _create_raw_disk(raw_path, size_mb)
    _raw_to_qcow2(raw_path, qcow2_path)
    raw_path.unlink()


class TestStorage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        test_command = ['qemu-img', '--version']
        retval = subprocess.run(test_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if retval.returncode != 0:
            raise RuntimeError(f"{test_command} failed with {retval.returncode}: {retval.stderr}")

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp_dir.name)

    def tearDown(self):
        self._tmp_dir.cleanup()

    def _create_root_disk(self) -> QCOWRootDisk:
        root_dir = self._tmp_path
        root_disk = root_dir / 'disk.qcow2'
        _create_qcow_disk(root_disk, 10)
        return QCOWRootDisk(self._tmp_path)

    def test_create_child(self):
        root_disk = self._create_root_disk()
        child = root_disk.get_diff('child')
        child.create().unlock()

    def test_get_snapshot_path(self):
        root_disk = self._create_root_disk()
        child = root_disk.get_diff('child')
        child.create().unlock()
        self.assertIsInstance(child.get_filesystem_path(), Path)

    def test_get_non_existing_child_path(self):
        root_disk = self._create_root_disk()
        child = root_disk.get_diff('child')
        with self.assertRaises(ChildNotExist):
            child.get_filesystem_path()

    def test_rename_child(self):
        root_disk = self._create_root_disk()
        child = root_disk.get_diff('child')
        child.create().unlock()
        renamed_child = child.rename('renamed_child')
        with self.assertRaises(ChildExists):
            renamed_child.create().unlock()

    def test_rename_non_existing_child(self):
        root_disk = self._create_root_disk()
        child = root_disk.get_diff('child')
        with self.assertRaises(ChildNotExist):
            child.rename('renamed_child')

    def test_remove_child(self):
        root_disk = self._create_root_disk()
        child = root_disk.get_diff('child')
        child.create().unlock()
        child.remove()

    def test_remove_non_existing_child(self):
        root_disk = self._create_root_disk()
        non_existing_child = root_disk.get_diff('non_existing_child')
        non_existing_child.remove()

    def test_attempt_create_existing_child(self):
        root_disk = self._create_root_disk()
        child = root_disk.get_diff('child')
        child.create().unlock()
        with self.assertRaises(ChildExists):
            child.create().unlock()

    def test_commit_snapshot_pending(self):
        root_disk = self._create_root_disk()
        pending_snapshot = PendingSnapshot(root_disk, 'child')
        pending_snapshot.commit()
        child = root_disk.get_diff('child')
        with self.assertRaises(ChildExists):
            child.create().unlock()

    def test_commit_snapshot_rollback(self):
        root_disk = self._create_root_disk()
        pending_snapshot = PendingSnapshot(root_disk, 'child')
        pending_snapshot.rollback()
        child = root_disk.get_diff('child')
        child.create().unlock()

    def test_pending_snapshot(self):
        root_disk = self._create_root_disk()
        _ = PendingSnapshot(root_disk, 'child')
        with self.assertRaises(SnapshotAlreadyPending):
            PendingSnapshot(root_disk, 'child')

    def test_snapshot_exist(self):
        root_disk = self._create_root_disk()
        child = root_disk.get_diff('child')
        child.create().unlock()
        with self.assertRaises(ChildExists):
            PendingSnapshot(root_disk, 'child')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
