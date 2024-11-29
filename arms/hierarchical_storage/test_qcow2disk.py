# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import logging
import subprocess
import tempfile
import unittest
from pathlib import Path

from arms.hierarchical_storage.qcow2disk import DiskExists
from arms.hierarchical_storage.qcow2disk import QCOW2ChildDisk
from arms.hierarchical_storage.qcow2disk import QCOW2Disk


def _qemu_img(*args: str):
    command = ['qemu-img', *args]
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as err:
        logging.error("Error at executing '%s'", ' '.join(command))
        raise RuntimeError(f"QEMU error: {err.stderr}")


def _raw_to_qcow2(raw: Path) -> Path:
    qcow2 = raw.with_suffix('.qcow2')
    logging.info("Converting %s => %s ...", raw, qcow2)
    _qemu_img('convert', '-f', 'raw', '-O', 'qcow2', str(raw), str(qcow2))
    return qcow2


def _qcow2_to_raw(qcow2: Path) -> Path:
    raw = qcow2.with_suffix('.img')
    logging.info("Converting %s => %s ...", qcow2, raw)
    _qemu_img('convert', '-f', 'qcow2', '-O', 'raw', str(qcow2), str(raw))
    return raw


def _md5(path: Path) -> str:
    hash_md5 = hashlib.md5()
    chunk_size_bytes = 1024 * 1024
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size_bytes), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


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


class TestQCOW2Create(unittest.TestCase):

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

    def test_create_child(self):
        raw_disk = self._tmp_path / 'disk.img'
        _create_raw_disk(raw_disk, 100)
        qcow2_disk = _raw_to_qcow2(raw_disk)
        parent_disk = QCOW2Disk(qcow2_disk)
        child_disk_path = qcow2_disk.with_name(f'{qcow2_disk.stem}_child.qcow2')
        child_disk = parent_disk.get_child(child_disk_path)
        child_disk.create()
        child_disk_raw = _qcow2_to_raw(child_disk_path)
        original_md5 = _md5(raw_disk)
        result_md5 = _md5(child_disk_raw)
        self.assertEqual(original_md5, result_md5)

    def test_create_dots_in_path(self):
        raw_disk = self._tmp_path / 'disk.img'
        _create_raw_disk(raw_disk, 100)
        parent_qcow2_disk = _raw_to_qcow2(raw_disk)
        inner_dir = self._tmp_path / 'inner'
        inner_dir.mkdir()
        child_disk_path = inner_dir / f'{parent_qcow2_disk.stem}_child.qcow2'
        relative_parent_path = Path(f'../././{parent_qcow2_disk.name}')
        child_disk = QCOW2ChildDisk(child_disk_path, relative_parent_path)
        child_disk.create()

    def test_remove(self):
        raw_disk = self._tmp_path / 'disk.img'
        _create_raw_disk(raw_disk, 100)
        qcow2_disk = _raw_to_qcow2(raw_disk)
        parent_disk = QCOW2Disk(qcow2_disk)
        child_disk_path = qcow2_disk.with_name(f'{qcow2_disk.stem}_child.qcow2')
        child_disk = parent_disk.get_child(child_disk_path)
        child_disk.create()
        child_disk.remove()
        self.assertFalse(child_disk_path.exists())

    def test_remove_non_existing(self):
        non_existing_parent = self._tmp_path / 'non_existing.qcow2'
        non_existing_child = self._tmp_path / 'non_existing_child.qcow2'
        parent_disk = QCOW2Disk(non_existing_parent)
        child_disk = parent_disk.get_child(non_existing_child)
        child_disk.remove()

    def test_already_exists(self):
        raw_disk = self._tmp_path / 'disk.img'
        _create_raw_disk(raw_disk, 100)
        qcow2_disk = _raw_to_qcow2(raw_disk)
        parent_disk = QCOW2Disk(qcow2_disk)
        child_disk_path = qcow2_disk.with_name(f'{qcow2_disk.stem}_child.qcow2')
        child_disk = parent_disk.get_child(child_disk_path)
        child_disk.create()
        md5_before = _md5(child_disk_path)
        mtime_before = child_disk_path.stat().st_mtime
        with self.assertRaises(DiskExists):
            child_disk.create()
        md5_after = _md5(child_disk_path)
        mtime_after = child_disk_path.stat().st_mtime
        self.assertEqual(md5_before, md5_after)
        self.assertEqual(mtime_before, mtime_after)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
