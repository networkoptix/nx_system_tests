# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from directories.prerequisites import make_prerequisite_store
from directories.prerequisites.dummy_http_server import http_server_serving


def test_prerequisites(exit_stack):
    http_server = exit_stack.enter_context(http_server_serving())
    remote_tmp_path = get_run_dir() / 'remote'
    remote_tmp_path.mkdir()
    local_tmp_path = get_run_dir() / 'local'
    local_tmp_path.mkdir()
    remote_test_prerequisite_path = remote_tmp_path / 'self-test/prerequisite-test.txt'
    remote_test_prerequisite_path.parent.mkdir()
    remote_test_prerequisite_path.write_text('test prerequisite\n')
    ip, port = http_server.server_address
    store = make_prerequisite_store(f"http://{ip}:{port}/remote", local_tmp_path)
    local_prerequisite_path = local_tmp_path / 'self-test/prerequisite-test.txt'
    assert not local_prerequisite_path.exists()
    path = store.fetch('self-test/prerequisite-test.txt')
    assert path == local_prerequisite_path
    assert path.read_text() == 'test prerequisite\n'
