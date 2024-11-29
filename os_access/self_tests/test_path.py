# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import errno
import hashlib
import logging
import os
import pprint
import time
from contextlib import AbstractContextManager
from contextlib import contextmanager
from pathlib import Path
from string import whitespace
from typing import Tuple
from typing import cast

from smb import smb_structs

from directories import get_run_dir
from os_access import RemotePath
from os_access import copy_file
from tests.infra import assert_raises
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types

_logger = logging.getLogger(__name__)


def _clean_up_dir(path):
    # To avoid duplication but makes setup and test distinct.
    path.rmtree(ignore_errors=True)
    path.mkdir(parents=True)  # Its parents may not exist.
    return path


def _remote_test_dir(temp_dir):
    base_remote_dir = temp_dir / (__name__ + '-remote')
    dirty_remote_test_dir = base_remote_dir / 'dir_name'
    _clean_up_dir(dirty_remote_test_dir)
    return dirty_remote_test_dir


def _existing_remote_file(remote_test_dir, existing_remote_file_size=65537):
    path = remote_test_dir / 'existing_file'
    path.write_bytes(os.urandom(existing_remote_file_size))
    return path


def _existing_remote_dir(remote_test_dir):
    path = remote_test_dir / 'existing_dir'
    path.mkdir()
    return path


@contextmanager
def _os_paths(
        path_type: str,
        artifacts_dir: Path,
        ) -> AbstractContextManager[Tuple[RemotePath, RemotePath]]:
    vm_pool = public_default_vm_pool(artifacts_dir)
    if path_type == 'smb':
        with vm_pool.clean_vm(vm_types['win11']) as windows_vm:
            windows_vm.os_access.wait_ready()
            with windows_vm.os_access.prepared_one_shot_vm(artifacts_dir):
                yield windows_vm.os_access.home(), windows_vm.os_access.tmp()
    elif path_type == 'sftp':
        with vm_pool.clean_vm(vm_types['ubuntu18']) as linux_vm:
            linux_vm.os_access.wait_ready()
            with linux_vm.os_access.prepared_one_shot_vm(artifacts_dir):
                yield linux_vm.os_access.home(), linux_vm.os_access.tmp()
    else:
        raise RuntimeError(f"Unsupported path type: {path_type}")


def test_home_smb():
    _test_home('smb')


def test_home_sftp():
    _test_home('sftp')


def _test_home(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [home_dir, _temp_dir]:
        assert home_dir.exists()


def test_mkdir_rmdir_smb():
    _test_mkdir_rmdir('smb')


def test_mkdir_rmdir_sftp():
    _test_mkdir_rmdir('sftp')


def _test_mkdir_rmdir(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [home_dir, _temp_dir]:
        path = home_dir / 'dir'
        with assert_raises(FileNotFoundError):
            path.rmdir()
        path.mkdir()
        with assert_raises(FileExistsError):
            path.mkdir()
        path.rmdir()


def test_rmdir_on_not_empty_smb():
    _test_rmdir_on_not_empty('smb')


def test_rmdir_on_not_empty_sftp():
    _test_rmdir_on_not_empty('sftp')


def _test_rmdir_on_not_empty(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_dir = _existing_remote_dir(remote_test_dir)
        path = existing_remote_dir / 'dir_for_rmdir'
        path.mkdir()
        path.joinpath('file_to_prevent_rmdir').write_bytes(b'dummy content')
        try:
            path.rmdir()
        except OSError as e:
            assert e.errno == errno.ENOTEMPTY
        else:
            raise Exception("Did not raise")


def test_rmtree_write_exists_smb():
    _test_rmtree_write_exists('smb')


def test_rmtree_write_exists_sftp():
    _test_rmtree_write_exists('sftp')


def _test_rmtree_write_exists(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        touched_file = remote_test_dir / 'touched.empty'
        assert not touched_file.exists()
        touched_file.write_bytes(b'')
        assert touched_file.exists()


def test_rmtree_mkdir_exists_smb_depth1():
    _test_rmtree_mkdir_exists('smb', 1)


def test_rmtree_mkdir_exists_smb_depth2():
    _test_rmtree_mkdir_exists('smb', 2)


def test_rmtree_mkdir_exists_smb_depth3():
    _test_rmtree_mkdir_exists('smb', 3)


def test_rmtree_mkdir_exists_smb_depth4():
    _test_rmtree_mkdir_exists('smb', 4)


def test_rmtree_mkdir_exists_sftp_depth1():
    _test_rmtree_mkdir_exists('sftp', 1)


def test_rmtree_mkdir_exists_sftp_depth2():
    _test_rmtree_mkdir_exists('sftp', 2)


def test_rmtree_mkdir_exists_sftp_depth3():
    _test_rmtree_mkdir_exists('sftp', 3)


def test_rmtree_mkdir_exists_sftp_depth4():
    _test_rmtree_mkdir_exists('sftp', 4)


def _test_rmtree_mkdir_exists(path_type, depth):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        root_dir = remote_test_dir / 'root'
        root_dir.mkdir()
        target_dir = root_dir.joinpath(*['level_{}'.format(level) for level in range(1, depth + 1)])
        assert not target_dir.exists()
        with assert_raises(FileNotFoundError):
            target_dir.rmtree(ignore_errors=False)  # Not exists, raise.
        target_dir.rmtree(ignore_errors=True)  # No effect even if parent doesn't exist.
        if depth == 1:
            target_dir.mkdir(parents=False)
        else:
            with assert_raises(FileNotFoundError):
                target_dir.mkdir(parents=False)
            target_dir.mkdir(parents=True)
        assert target_dir.exists()
        target_file = target_dir.joinpath('deep_file')
        assert not target_file.exists()
        target_file.write_bytes(b'')
        assert target_file.exists()
        root_dir.rmtree()
        assert not root_dir.exists()


_tricky_bytes = dict([
    ('chr0_to_chr255', bytes(bytearray(range(0x100)))),
    ('chr0_to_chr255_100times', bytes(bytearray(range(0x100)) * 100)),
    ('whitespace', whitespace.encode()),
    ('windows_newlines', b'\r\n' * 100),
    ('linux_newlines', b'\n' * 100),
    ('ending_with_chr0', b'abc\0'),
    ])


def test_write_read_bytes_smb_chr0_to_chr255():
    _test_write_read_bytes('smb', ('chr0_to_chr255', _tricky_bytes['chr0_to_chr255']))


def test_write_read_bytes_smb_chr0_to_chr255_100times():
    _test_write_read_bytes('smb', ('chr0_to_chr255_100times', _tricky_bytes['chr0_to_chr255_100times']))


def test_write_read_bytes_smb_whitespace():
    _test_write_read_bytes('smb', ('whitespace', _tricky_bytes['whitespace']))


def test_write_read_bytes_smb_windows_newlines():
    _test_write_read_bytes('smb', ('windows_newlines', _tricky_bytes['windows_newlines']))


def test_write_read_bytes_smb_linux_newlines():
    _test_write_read_bytes('smb', ('linux_newlines', _tricky_bytes['linux_newlines']))


def test_write_read_bytes_smb_ending_with_chr0():
    _test_write_read_bytes('smb', ('ending_with_chr0', _tricky_bytes['ending_with_chr0']))


def test_write_read_bytes_sftp_chr0_to_chr255():
    _test_write_read_bytes('sftp', ('chr0_to_chr255', _tricky_bytes['chr0_to_chr255']))


def test_write_read_bytes_sftp_chr0_to_chr255_100times():
    _test_write_read_bytes('sftp', ('chr0_to_chr255_100times', _tricky_bytes['chr0_to_chr255_100times']))


def test_write_read_bytes_sftp_whitespace():
    _test_write_read_bytes('sftp', ('whitespace', _tricky_bytes['whitespace']))


def test_write_read_bytes_sftp_windows_newlines():
    _test_write_read_bytes('sftp', ('windows_newlines', _tricky_bytes['windows_newlines']))


def test_write_read_bytes_sftp_linux_newlines():
    _test_write_read_bytes('sftp', ('linux_newlines', _tricky_bytes['linux_newlines']))


def test_write_read_bytes_sftp_ending_with_chr0():
    _test_write_read_bytes('sftp', ('ending_with_chr0', _tricky_bytes['ending_with_chr0']))


def _test_write_read_bytes(path_type, data):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        name, written = data
        file_path = remote_test_dir / '{}.dat'.format(name)
        file_path.write_bytes(written)
        read = file_path.read_bytes()
        assert read == written


def test_write_read_bytes_many_times_smb():
    _test_write_read_bytes_many_times('smb')


def test_write_read_bytes_many_times_sftp():
    _test_write_read_bytes_many_times('sftp')


def _test_write_read_bytes_many_times(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        file_path = remote_test_dir / 'small_data.dat'
        file_path.write_bytes(b'abc')
        for _ in range(1000):
            read = file_path.read_bytes()
            assert read == b'abc'


def test_write_read_tricky_bytes_with_offsets_smb_chr0_to_chr255():
    _test_write_read_tricky_bytes_with_offsets('smb', ('chr0_to_chr255', _tricky_bytes['chr0_to_chr255']))


def test_write_read_tricky_bytes_with_offsets_smb_chr0_to_chr255_100times():
    _test_write_read_tricky_bytes_with_offsets('smb', ('chr0_to_chr255_100times', _tricky_bytes['chr0_to_chr255_100times']))


def test_write_read_tricky_bytes_with_offsets_smb_whitespace():
    _test_write_read_tricky_bytes_with_offsets('smb', ('whitespace', _tricky_bytes['whitespace']))


def test_write_read_tricky_bytes_with_offsets_smb_windows_newlines():
    _test_write_read_tricky_bytes_with_offsets('smb', ('windows_newlines', _tricky_bytes['windows_newlines']))


def test_write_read_tricky_bytes_with_offsets_smb_linux_newlines():
    _test_write_read_tricky_bytes_with_offsets('smb', ('linux_newlines', _tricky_bytes['linux_newlines']))


def test_write_read_tricky_bytes_with_offsets_smb_ending_with_chr0():
    _test_write_read_tricky_bytes_with_offsets('smb', ('ending_with_chr0', _tricky_bytes['ending_with_chr0']))


def test_write_read_tricky_bytes_with_offsets_sftp_chr0_to_chr255():
    _test_write_read_tricky_bytes_with_offsets('sftp', ('chr0_to_chr255', _tricky_bytes['chr0_to_chr255']))


def test_write_read_tricky_bytes_with_offsets_sftp_chr0_to_chr255_100times():
    _test_write_read_tricky_bytes_with_offsets('sftp', ('chr0_to_chr255_100times', _tricky_bytes['chr0_to_chr255_100times']))


def test_write_read_tricky_bytes_with_offsets_sftp_whitespace():
    _test_write_read_tricky_bytes_with_offsets('sftp', ('whitespace', _tricky_bytes['whitespace']))


def test_write_read_tricky_bytes_with_offsets_sftp_windows_newlines():
    _test_write_read_tricky_bytes_with_offsets('sftp', ('windows_newlines', _tricky_bytes['windows_newlines']))


def test_write_read_tricky_bytes_with_offsets_sftp_linux_newlines():
    _test_write_read_tricky_bytes_with_offsets('sftp', ('linux_newlines', _tricky_bytes['linux_newlines']))


def test_write_read_tricky_bytes_with_offsets_sftp_ending_with_chr0():
    _test_write_read_tricky_bytes_with_offsets('sftp', ('ending_with_chr0', _tricky_bytes['ending_with_chr0']))


def _test_write_read_tricky_bytes_with_offsets(path_type, data):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        name, written = data
        file_path = remote_test_dir / '{}.dat'.format(name)
        file_path.write_bytes(b'aaaaaaaaaa')
        with file_path.open('rb+') as f:
            f.seek(10)
            f.write(written)
        with file_path.open('rb+') as f:
            f.seek(10)
            assert f.read(100) == written[:100]


def test_write_read_bytes_with_tricky_offsets_smb():
    _test_write_read_bytes_with_tricky_offsets('smb')


def test_write_read_bytes_with_tricky_offsets_sftp():
    _test_write_read_bytes_with_tricky_offsets('sftp')


def _test_write_read_bytes_with_tricky_offsets(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        file_path = remote_test_dir / 'abc.dat'
        file_path.write_bytes(b'aaaaa')
        with file_path.open('rb+') as f:
            f.seek(5)
            f.write(b'bbbbb')
        with file_path.open('rb+') as f:
            f.seek(10)
            f.write(b'ccccc')
        with file_path.open('rb+') as f:
            f.seek(12)
            assert f.read(5) == b'ccc'
        with file_path.open('rb+') as f:
            f.seek(8)
            assert f.read(5) == b'bbccc'
        with file_path.open('rb+') as f:
            f.seek(3)
            assert f.read(5) == b'aabbb'


def test_write_read_text_smb_latin_ascii():
    _test_write_read_text('smb', ('latin', 'ascii', "Two wrongs don't make a right.\nThe pen is mightier than the sword."))


def test_write_read_text_smb_latin_utf8():
    _test_write_read_text('smb', ('latin', 'utf8', 'Alla sätt är bra utom de dåliga.\nGräv där du står.'))


def test_write_read_text_smb_cyrillic_utf8():
    _test_write_read_text('smb', ('cyrillic', 'utf8', 'А дело бывало — и коза волка съедала.\nАзбука — к мудрости ступенька.'))


def test_write_read_text_smb_cyrillic_utf16():
    _test_write_read_text('smb', ('cyrillic', 'utf16', 'Загляне сонца і ў наша аконца.\nКаб свiнне poгi - нiкому б не было дарогi.'))


def test_write_read_text_smb_pinyin_utf8():
    _test_write_read_text('smb', ('pinyin', 'utf8', '防人之心不可無。\n福無重至,禍不單行。'))


def test_write_read_text_smb_pinyin_utf16():
    _test_write_read_text('smb', ('pinyin', 'utf16', '[与其]临渊羡鱼，不如退而结网。\n君子之心不胜其小，而气量涵盖一世。'))


def test_write_read_text_sftp_latin_ascii():
    _test_write_read_text('sftp', ('latin', 'ascii', "Two wrongs don't make a right.\nThe pen is mightier than the sword."))


def test_write_read_text_sftp_latin_utf8():
    _test_write_read_text('sftp', ('latin', 'utf8', 'Alla sätt är bra utom de dåliga.\nGräv där du står.'))


def test_write_read_text_sftp_cyrillic_utf8():
    _test_write_read_text('sftp', ('cyrillic', 'utf8', 'А дело бывало — и коза волка съедала.\nАзбука — к мудрости ступенька.'))


def test_write_read_text_sftp_cyrillic_utf16():
    _test_write_read_text('sftp', ('cyrillic', 'utf16', 'Загляне сонца і ў наша аконца.\nКаб свiнне poгi - нiкому б не было дарогi.'))


def test_write_read_text_sftp_pinyin_utf8():
    _test_write_read_text('sftp', ('pinyin', 'utf8', '防人之心不可無。\n福無重至,禍不單行。'))


def test_write_read_text_sftp_pinyin_utf16():
    _test_write_read_text('sftp', ('pinyin', 'utf16', '[与其]临渊羡鱼，不如退而结网。\n君子之心不胜其小，而气量涵盖一世。'))


def _test_write_read_text(path_type, data):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        name, encoding, written = data
        file_path = remote_test_dir / '{}_{}.txt'.format(name, encoding)
        chars_written = file_path.write_text(written, encoding=encoding)
        assert chars_written == len(written)
        read = file_path.read_text(encoding=encoding)
        assert read == written


def test_write_to_dir_smb():
    _test_write_to_dir('smb')


def test_write_to_dir_sftp():
    _test_write_to_dir('sftp')


def _test_write_to_dir(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_dir = _existing_remote_dir(remote_test_dir)
        with assert_raises((IsADirectoryError, PermissionError)):
            existing_remote_dir.write_bytes(os.urandom(1000))


def _path_with_file_in_parents(depth, path):
    for level in range(1, depth + 1):
        path /= 'level_{}'.format(level)
    return path


def test_write_when_parent_is_a_file_smb_depth1():
    _test_write_when_parent_is_a_file('smb', 1)


def test_write_when_parent_is_a_file_smb_depth2():
    _test_write_when_parent_is_a_file('smb', 2)


def test_write_when_parent_is_a_file_smb_depth3():
    _test_write_when_parent_is_a_file('smb', 3)


def test_write_when_parent_is_a_file_sftp_depth1():
    _test_write_when_parent_is_a_file('sftp', 1)


def test_write_when_parent_is_a_file_sftp_depth2():
    _test_write_when_parent_is_a_file('sftp', 2)


def test_write_when_parent_is_a_file_sftp_depth3():
    _test_write_when_parent_is_a_file('sftp', 3)


def _test_write_when_parent_is_a_file(path_type, depth):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_file = _existing_remote_file(remote_test_dir)
        path_with_file_in_parents = _path_with_file_in_parents(depth, existing_remote_file)
        with assert_raises((NotADirectoryError, FileNotFoundError)):
            path_with_file_in_parents.write_bytes(b'anything')


def test_mkdir_when_parent_is_a_file_smb_depth1():
    _test_mkdir_when_parent_is_a_file('smb', 1)


def test_mkdir_when_parent_is_a_file_smb_depth2():
    _test_mkdir_when_parent_is_a_file('smb', 2)


def test_mkdir_when_parent_is_a_file_smb_depth3():
    _test_mkdir_when_parent_is_a_file('smb', 3)


def test_mkdir_when_parent_is_a_file_sftp_depth1():
    _test_mkdir_when_parent_is_a_file('sftp', 1)


def test_mkdir_when_parent_is_a_file_sftp_depth2():
    _test_mkdir_when_parent_is_a_file('sftp', 2)


def test_mkdir_when_parent_is_a_file_sftp_depth3():
    _test_mkdir_when_parent_is_a_file('sftp', 3)


def _test_mkdir_when_parent_is_a_file(path_type, depth):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_file = _existing_remote_file(remote_test_dir)
        path_with_file_in_parents = _path_with_file_in_parents(depth, existing_remote_file)
        with assert_raises((NotADirectoryError, FileNotFoundError)):
            path_with_file_in_parents.mkdir()


def test_read_from_dir_smb():
    _test_read_from_dir('smb')


def test_read_from_dir_sftp():
    _test_read_from_dir('sftp')


def _test_read_from_dir(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_dir = _existing_remote_dir(remote_test_dir)
        with assert_raises((IsADirectoryError, PermissionError)):
            _ = existing_remote_dir.read_bytes()


def test_unlink_dir_smb():
    _test_unlink_dir('smb')


def test_unlink_dir_sftp():
    _test_unlink_dir('sftp')


def _test_unlink_dir(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_dir = _existing_remote_dir(remote_test_dir)
        with assert_raises((IsADirectoryError, PermissionError)):
            existing_remote_dir.unlink()


def test_unlink_non_existent_smb():
    _test_unlink_non_existent('smb')


def test_unlink_non_existent_sftp():
    _test_unlink_non_existent('sftp')


def _test_unlink_non_existent(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_dir = _existing_remote_dir(remote_test_dir)
        with assert_raises(FileNotFoundError):
            existing_remote_dir.joinpath('non-existent').unlink()


def test_write_to_existing_file_smb():
    _test_write_to_existing_file('smb')


def test_write_to_existing_file_sftp():
    _test_write_to_existing_file('sftp')


def _test_write_to_existing_file(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_file = _existing_remote_file(remote_test_dir)
        data = os.urandom(1000)
        existing_remote_file.write_bytes(data)
        assert existing_remote_file.read_bytes() == data


def test_read_from_non_existent_smb():
    _test_read_from_non_existent('smb')


def test_read_from_non_existent_sftp():
    _test_read_from_non_existent('sftp')


def _test_read_from_non_existent(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        non_existent_file = remote_test_dir / 'non_existent'
        with assert_raises(FileNotFoundError):
            _ = non_existent_file.read_bytes()


def test_size_smb():
    _test_size('smb')


def test_size_sftp():
    _test_size('sftp')


def _test_size(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        path = remote_test_dir / 'to_measure_size.dat'
        path.write_bytes(b'X' * 100500)
        assert path.size() == 100500


def test_size_of_nonexistent_smb():
    _test_size_of_nonexistent('smb')


def test_size_of_nonexistent_sftp():
    _test_size_of_nonexistent('sftp')


def _test_size_of_nonexistent(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        path = remote_test_dir / 'to_measure_size.dat'
        with assert_raises(FileNotFoundError):
            path.size()


def test_size_of_a_dir_smb():
    _test_size_of_a_dir('smb')


def test_size_of_a_dir_sftp():
    _test_size_of_a_dir('sftp')


def _test_size_of_a_dir(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        path = remote_test_dir / 'to_measure_size.dat'
        path.mkdir()
        with assert_raises(IsADirectoryError):
            path.size()


def test_glob_on_file_smb():
    _test_glob_on_file('smb')


def test_glob_on_file_sftp():
    _test_glob_on_file('sftp')


def _test_glob_on_file(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_file = _existing_remote_file(remote_test_dir)
        assert not list(existing_remote_file.glob('*'))


def test_glob_recursive_smb():
    _test_glob_recursive('smb')


def test_glob_recursive_sftp():
    _test_glob_recursive('sftp')


def _test_glob_recursive(path_type):
    artifacts_dir = get_run_dir()
    layout = [
        ('1',),
        ('1', '11'),
        ('1', '11', '111.txt'),
        ('1', '11', '112.dat'),
        ('1', '11', '113'),
        ('1', '11', '113', '1131'),
        ('1', '12'),
        ('1', '13.txt'),
        ('2',),
        ('3.txt',),
        ]
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_dir = _existing_remote_dir(remote_test_dir)
        for simplified in layout:
            path = existing_remote_dir.joinpath(*simplified)
            if path.suffix == '.txt':
                path.write_text('dummy text :)')
            elif path.suffix == '.dat':
                path.write_bytes(b'dummy bytes \x8D')
            else:
                path.mkdir()

    def _glob(pattern):
        _logger.debug('Glob: %s', pattern)
        raw = list(existing_remote_dir.glob(pattern))
        _logger.debug('Raw:\n%s', pprint.pformat(raw))
        simplified = list(sorted(path.relative_to(existing_remote_dir).parts for path in raw))
        _logger.debug('Simplified:\n%s', pprint.pformat(simplified))
        return simplified

    assert _glob('**') == [
        (),
        ('1',),
        ('1', '11'),
        ('1', '11', '113'),
        ('1', '11', '113', '1131'),
        ('1', '12'),
        ('2',),
        ]
    assert _glob('**/*') == [
        ('1',),
        ('1', '11'),
        ('1', '11', '111.txt'),
        ('1', '11', '112.dat'),
        ('1', '11', '113'),
        ('1', '11', '113', '1131'),
        ('1', '12'),
        ('1', '13.txt'),
        ('2',),
        ('3.txt',),
        ]
    assert _glob('**/*.txt') == [
        ('1', '11', '111.txt'),
        ('1', '13.txt'),
        ('3.txt',),
        ]
    assert _glob('**/*.dat') == [
        ('1', '11', '112.dat'),
        ]


def test_glob_on_non_existent_smb():
    _test_glob_on_non_existent('smb')


def test_glob_on_non_existent_sftp():
    _test_glob_on_non_existent('sftp')


def _test_glob_on_non_existent(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_dir = _existing_remote_dir(remote_test_dir)
        non_existent_path = existing_remote_dir / 'non_existent'
        assert not list(non_existent_path.glob('*'))


def test_glob_on_empty_dir_smb():
    _test_glob_on_empty_dir('smb')


def test_glob_on_empty_dir_sftp():
    _test_glob_on_empty_dir('sftp')


def _test_glob_on_empty_dir(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_dir = _existing_remote_dir(remote_test_dir)
        assert not list(existing_remote_dir.glob('*'))


def test_glob_no_result_smb():
    _test_glob_no_result('smb')


def test_glob_no_result_sftp():
    _test_glob_no_result('sftp')


def _test_glob_no_result(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_dir = _existing_remote_dir(remote_test_dir)
        existing_remote_dir.joinpath('oi.existing').write_bytes(b'empty')
        assert not list(existing_remote_dir.glob('*.non_existent'))


def test_many_mkdir_rmtree_smb_2iterations_depth2():
    _test_many_mkdir_rmtree('smb', 2, 2)


def test_many_mkdir_rmtree_smb_2iterations_depth10():
    _test_many_mkdir_rmtree('smb', 2, 10)


def test_many_mkdir_rmtree_smb_10iterations_depth2():
    _test_many_mkdir_rmtree('smb', 10, 2)


def test_many_mkdir_rmtree_smb_10iterations_depth10():
    _test_many_mkdir_rmtree('smb', 10, 10)


def test_many_mkdir_rmtree_sftp_2iterations_depth2():
    _test_many_mkdir_rmtree('sftp', 2, 2)


def test_many_mkdir_rmtree_sftp_2iterations_depth10():
    _test_many_mkdir_rmtree('sftp', 2, 10)


def test_many_mkdir_rmtree_sftp_10iterations_depth2():
    _test_many_mkdir_rmtree('sftp', 10, 2)


def test_many_mkdir_rmtree_sftp_10iterations_depth10():
    _test_many_mkdir_rmtree('sftp', 10, 10)


def _test_many_mkdir_rmtree(path_type, iterations, depth):
    artifacts_dir = get_run_dir()
    """Sometimes mkdir after rmtree fails because of pending delete operations."""
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        top_path = remote_test_dir / 'top'
        deep_path = top_path.joinpath(*('level{}'.format(level) for level in range(depth)))
        for _ in range(iterations):
            deep_path.mkdir(parents=True)
            deep_path.joinpath('treasure').write_bytes(b'\0' * 1000000)
            top_path.rmtree()


def test_copy_file_smb_small():
    _test_copy_file('smb', 111222)


def test_copy_file_sftp_small():
    _test_copy_file('sftp', 111222)


def test_copy_file_smb_empty():
    _test_copy_file('smb', 0)


def test_copy_file_sftp_empty():
    _test_copy_file('sftp', 0)


def test_copy_file_smb_byte():
    _test_copy_file('smb', 1)


def test_copy_file_sftp_byte():
    _test_copy_file('sftp', 1)


def test_copy_file_smb_big():
    _test_copy_file('smb', 111222333)


def test_copy_file_sftp_big():
    _test_copy_file('sftp', 111222333)


def _test_copy_file(path_type, file_size):
    artifacts_dir = get_run_dir()
    local_test_dir = artifacts_dir / 'test_path-local'
    local_test_dir.mkdir(parents=True, exist_ok=True)
    with _os_paths(path_type, artifacts_dir) as [_home_dir, temp_dir]:
        remote_test_dir = _remote_test_dir(temp_dir)
        existing_remote_dir = _existing_remote_dir(remote_test_dir)
        source = local_test_dir / 'source'
        middle = existing_remote_dir / 'middle'
        destination = local_test_dir / 'destination'
        source.write_bytes(os.urandom(file_size))
        copy_file(source, middle)
        assert middle.stat().st_size == file_size
        copy_file(middle, destination)
        assert destination.stat().st_size == middle.stat().st_size
        if file_size < 1000:
            assert destination.read_bytes() == source.read_bytes()
        else:
            # Avoid comparing full contents of big files. On failure, pytest looks
            # for the longest matching parts, and it takes forever on large inputs.
            destination_bytes = destination.read_bytes()
            assert destination_bytes
            source_bytes = source.read_bytes()
            assert source_bytes
            # Do checks that can show something that hashes cannot.
            assert destination_bytes[:1000] == source_bytes[:1000]
            assert len(destination_bytes) == len(source_bytes)
            assert destination_bytes[-1000:] == source_bytes[-1000:]
            # Checking hashes is the best that can be done.
            destination_hash = hashlib.sha1(destination_bytes).hexdigest()
            source_hash = hashlib.sha1(source_bytes).hexdigest()
            assert destination_hash == source_hash


def test_mtime_smb():
    _test_mtime('smb')


def test_mtime_sftp():
    _test_mtime('sftp')


def _test_mtime(path_type):
    artifacts_dir = get_run_dir()
    with _os_paths(path_type, artifacts_dir) as (_home_dir, temp_dir):
        first_file = temp_dir / 'first.file'
        second_file = temp_dir / 'second.file'
        third_file = temp_dir / 'third.file'
        first_file.write_bytes(b'irrelevant')
        time.sleep(1)
        second_file.write_bytes(b'irrelevant')
        time.sleep(1)
        third_file.write_bytes(b'irrelevant')
        time.sleep(1)
        first_mtime = first_file.stat().st_mtime
        second_mtime = second_file.stat().st_mtime
        third_mtime = third_file.stat().st_mtime
    logging.info("%s st_mtime is %s", first_file, first_mtime)
    logging.info("%s st_mtime is %s", second_file, second_mtime)
    logging.info("%s st_mtime is %s", third_file, third_mtime)
    assert first_mtime < second_mtime < third_mtime


def test_correct_handling_of_smb_messages():
    # See: _store_smb_messages() in os_access/_smb_path.py
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    operation_failure = None
    with vm_pool.clean_vm(vm_types['win11']) as windows_vm:
        windows_vm.os_access.wait_ready()
        with windows_vm.os_access.prepared_one_shot_vm(artifacts_dir):
            registry_file = windows_vm.os_access.path(r'C:\Windows\System32\config\SYSTEM')
            try:
                registry_file.read_bytes()
            except PermissionError as exc:
                operation_failure = cast(smb_structs.OperationFailure, exc.__context__)
    assert operation_failure is not None, 'An exception is expected'
    assert isinstance(operation_failure, smb_structs.OperationFailure), 'The OperationFailure exception is expected'
    for message in operation_failure.smb_messages:
        if message.status == 0xC0000043:
            break
    else:
        raise RuntimeError('It should be an SMB message with the status 0xC0000043') from operation_failure
