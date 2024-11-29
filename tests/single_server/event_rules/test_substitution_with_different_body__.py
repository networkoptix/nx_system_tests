# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import HttpAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.event_rules.common import event
from tests.single_server.event_rules.common import expected
from tests.single_server.event_rules.common import http_server
from tests.single_server.event_rules.common import url_for


def _test_substitution_with_different_body(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    server = one_mediaserver.mediaserver()
    api = server.api
    params = {
        "source": "test_source",
        "caption": "test_caption",
        "description": "test_description",
        }
    httpserver = exit_stack.enter_context(http_server())
    url = url_for(port=httpserver.port, hostname=server.os_access.source_address(), uri='/')
    with event(api, HttpAction(url, {'text': ''}), params), httpserver.wait() as request:
        assert request.text == expected('', params)
    with event(api, HttpAction(url, {'text': '{none.}'}), params), httpserver.wait() as request:
        assert request.text == expected('{none.}', params)
    payload = '{event.source}'
    with event(api, HttpAction(url, {'text': payload}), params), httpserver.wait() as request:
        assert request.text == expected('{event.source}', params)
    payload = '{event.source} with {event.caption} and {event.description}'
    with event(api, HttpAction(url, {'text': payload}), params), httpserver.wait() as request:
        assert request.text == expected(payload, params)
    payload = '{event.source}t.source}t.source}" where source is "{even'
    with event(api, HttpAction(url, {'text': payload}), params), httpserver.wait() as request:
        assert request.text == expected(payload, params)
