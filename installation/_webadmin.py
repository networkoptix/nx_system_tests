# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import logging

from directories import get_ft_artifacts_root
from directories.prerequisites import make_prerequisite_store
from mediaserver_api import MediaserverApiV2

_logger = logging.getLogger(__name__)


def upload_web_admin_to_mediaserver(mediaserver_api: MediaserverApiV2, webadmin_url: str):
    if webadmin_url.startswith('builtin:'):
        _logger.info("Using builtin WebAdmin")
        return
    _logger.info("Going to upload %r WebAdmin to %r", webadmin_url, mediaserver_api)
    webadmin_dir = base64.urlsafe_b64encode(webadmin_url.encode()).decode()
    cache_dir = get_ft_artifacts_root() / 'webadmin-builds' / webadmin_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    store = make_prerequisite_store(webadmin_url, cache_dir)
    customization = mediaserver_api.get_server_info().customization
    blob_path = store.fetch(f'{customization}/external.dat')
    mediaserver_api.upload_static_web_content(blob_path.read_bytes())
