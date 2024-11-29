# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import BadRequest
from mediaserver_api import HttpAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.event_rules.common import event
from tests.single_server.event_rules.common import http_server
from tests.single_server.event_rules.common import url_for


def _test_method(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    server = one_mediaserver.mediaserver()
    api = server.api
    httpserver = exit_stack.enter_context(http_server())
    url = url_for(httpserver.port, server.os_access.source_address(), '/')
    with event(api, HttpAction(url, {'httpMethod': 'GET'})), httpserver.wait() as request:
        assert request.status_line == 'GET / HTTP/1.1'
    with event(api, HttpAction(url, {'httpMethod': 'POST'})), httpserver.wait() as request:
        assert request.status_line == 'POST / HTTP/1.1'
    with event(api, HttpAction(url, {'httpMethod': 'PUT'})), httpserver.wait() as request:
        assert request.status_line == 'PUT / HTTP/1.1'
    with event(api, HttpAction(url, {'httpMethod': 'DELETE'})), httpserver.wait() as request:
        assert request.status_line == 'DELETE / HTTP/1.1'
    with event(api, HttpAction(url, {'text': 'payload'})), httpserver.wait() as request:
        assert request.text == 'payload'
    with event(api, HttpAction(url)), httpserver.wait() as request:
        assert request.method == 'GET'
    # According to https://networkoptix.atlassian.net/browse/VMS-20775
    # incorrect HTTP method names are rejected.
    try:
        with event(api, HttpAction(url, {'httpMethod': 'INCORRECT_METHOD'})):
            pass
    except BadRequest as err:
        assert err.http_status == 400
    else:
        raise RuntimeError("The request with incorrect HTTP method name should not succeed")
