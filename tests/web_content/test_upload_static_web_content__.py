# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import io
import zipfile

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import OldSessionToken
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises
from tests.web_content.common import make_session_old


def _test_upload_static_web_content(distrib_url, one_vm_type, api_version, custom_summary, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    static_web_content = installer_supplier.static_web_content()
    custom_content = custom_static_web_content(static_web_content, custom_summary)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    server = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    server.start()
    api.setup_local_system()
    api.upload_static_web_content(custom_content)
    static_web_content_info = api.get_static_web_content_info()
    assert static_web_content_info['source'] == 'manual'
    assert static_web_content_info['details']['summary'] == custom_summary
    api.restart()
    static_web_content_info = api.get_static_web_content_info()
    assert static_web_content_info['source'] == 'manual'
    assert static_web_content_info['details']['summary'] == custom_summary
    make_session_old(server)
    api.disable_auth_refresh()
    with assert_raises(OldSessionToken):
        api.upload_static_web_content(custom_content)


def custom_static_web_content(static_web_content, custom_summary) -> bytes:
    with zipfile.ZipFile(static_web_content.path, 'r') as zip_in:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_out:
            for file in zip_in.filelist:
                if file.filename.endswith('version.txt'):
                    original_details = zip_in.read(file.filename).decode('utf-8')
                    custom_details = []
                    for line in original_details.splitlines():
                        k, v = line.split(': ', maxsplit=1)
                        if k == 'summary':
                            v = custom_summary
                        custom_details.append(f'{k}: {v}')
                    custom_details = '\n'.join(custom_details)
                    zip_out.writestr(file.filename, custom_details)
                else:
                    zip_out.writestr(file.filename, zip_in.read(file.filename))
    return buffer.getvalue()
