# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from threading import Thread

from directories.filelocker import AlreadyLocked
from directories.filelocker import try_lock_exclusively
from directories.filelocker import try_lock_shared
from directories.filelocker import try_locked
from directories.filelocker import wait_locked_exclusively
from directories.filelocker import wait_until_locked


class TestFileLocker(unittest.TestCase):

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp_dir.name)

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_try_lock_success(self):
        lock_file = self._tmp_path / "file.lock"
        with try_locked(lock_file):
            pass

    def test_try_lock_fail(self):
        lock_file = self._tmp_path / "file.lock"
        with try_locked(lock_file):
            with self.assertRaises(AlreadyLocked, msg=lock_file.name):
                with try_locked(lock_file):
                    raise RuntimeError("Second lock must not succeed")

    def test_try_locked_sequential(self):
        lock_file = self._tmp_path / "file.lock"
        with try_locked(lock_file):
            pass
        with try_locked(lock_file):
            pass

    def test_wait_locked(self):
        lock_file = self._tmp_path / "file.lock"
        with wait_locked_exclusively(lock_file, timeout_sec=1):
            pass

    def test_wait_locked_concurrent(self):
        lock_file = self._tmp_path / "file.lock"

        locked_event = Event()
        lock_thread = Thread(target=_locker_thread, args=(lock_file, locked_event), daemon=True)
        lock_thread.start()
        if not locked_event.wait(2):
            raise RuntimeError(f"Test is broken. {lock_file} is not locked after 2 sec")
        logging.info("Main: Waiting for %s is unlocked...", lock_file)
        with wait_locked_exclusively(lock_file, 10):
            logging.info("Main: %s is locked", lock_file)

    def test_exception_in_context(self):

        class _LocalException(Exception):
            pass

        lock_file = self._tmp_path / "file.lock"

        locked_event = Event()
        lock_thread = Thread(target=_locker_thread, args=(lock_file, locked_event), daemon=True)
        lock_thread.start()
        if not locked_event.wait(2):
            raise RuntimeError(f"Test is broken. {lock_file} is not locked after 2 sec")
        logging.info("Main: Waiting for %s is unlocked...", lock_file)
        with self.assertRaises(_LocalException):
            with wait_locked_exclusively(lock_file, 10):
                raise _LocalException("IRRELEVANT")

    def test_try_locked_read_file(self):
        lock_file = self._tmp_path / "file.lock"
        data_written = Path(__file__).read_bytes()
        lock_file.write_bytes(data_written)
        with try_locked(lock_file):
            pass
        data_read = lock_file.read_bytes()
        assert data_written == data_read

    def test_wait_locked_read_file(self):
        lock_file = self._tmp_path / "file.lock"
        data_written = Path(__file__).read_bytes()
        lock_file.write_bytes(data_written)
        with wait_locked_exclusively(lock_file, timeout_sec=2):
            pass
        data_read = lock_file.read_bytes()
        assert data_written == data_read

    def test_locked_unconditionally_concurrent(self):
        lock_file = self._tmp_path / "file.lock"

        locked_event = Event()
        lock_thread = Thread(target=_locker_thread, args=(lock_file, locked_event), daemon=True)
        lock_thread.start()
        if not locked_event.wait(2):
            raise RuntimeError(f"Test is broken. {lock_file} is not locked after 2 sec")
        logging.info("Main: Waiting for %s is unlocked...", lock_file)
        with wait_until_locked(lock_file):
            logging.info("Main: %s is locked", lock_file)

    def test_change_exclusive_lock_to_shared(self):
        lock_file = self._tmp_path / "file.lock"
        lock_file.touch(exist_ok=True)
        with lock_file.open('rb') as fd:
            fileno = fd.fileno()
            assert try_lock_exclusively(fileno)
            assert try_lock_shared(fileno)


def _locker_thread(lock_file: Path, locked_event: Event):
    try:
        delay_sec = 1
        logging.info("Thread: Lock file %s", lock_file)
        with try_locked(lock_file):
            logging.info("Thread: Holding file %s for %s sec ...", lock_file, delay_sec)
            locked_event.set()
            time.sleep(delay_sec)
    except Exception:
        logging.exception("Exception happened in the locker thread!")
        raise
    logging.info("Thread: Unlocked file %s", lock_file)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
