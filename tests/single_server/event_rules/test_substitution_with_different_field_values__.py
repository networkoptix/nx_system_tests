# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import HttpAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.event_rules.common import event
from tests.single_server.event_rules.common import expected
from tests.single_server.event_rules.common import http_server
from tests.single_server.event_rules.common import url_for


def _test_substitution_with_different_field_values(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    server = one_mediaserver.mediaserver()
    api = server.api
    httpserver = exit_stack.enter_context(http_server())
    url = url_for(httpserver.port, server.os_access.source_address(), '/')
    payload = '{event.source} with {event.caption} and {event.description}'
    params = {'source': 'test_src', 'caption': 'test_caption', 'description': 'test_desc'}
    with event(api, HttpAction(url, {'text': payload}), params), httpserver.wait() as request:
        assert request.text == expected(payload, params)
    params = {'source': ' test_src', 'caption': '\0test-capt', 'description': 'test_desc\0'}
    with event(api, HttpAction(url, {'text': payload}), params), httpserver.wait() as request:
        assert request.text == expected(payload, params)
    with event(api, HttpAction(url, {'text': payload}), {'source': ' test_src'}):
        with httpserver.wait() as request:
            assert request.text == expected(payload, {'source': ' test_src'})
    with event(api, HttpAction(url, {'text': payload}), {'caption': 'test_caption'}):
        with httpserver.wait() as request:
            assert request.text == expected(payload, {'caption': 'test_caption'})
    with event(api, HttpAction(url, {'text': payload}), {'description': 'test_desc'}):
        with httpserver.wait() as request:
            assert request.text == expected(payload, {'description': 'test_desc'})
