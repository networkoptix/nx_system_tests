# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from infrastructure.testrail_service._testrail_api import DEFAULT_TESTRAIL_URL
from infrastructure.testrail_service._testrail_api import TestrailApi
from infrastructure.testrail_service._testrail_api import TestrailClient
from infrastructure.testrail_service._testrail_cache import CacheResponseDecorator
from infrastructure.testrail_service._testrail_cache import DEFAULT_CACHE_PATH


def main():
    started_at = time.monotonic()
    testrail_api = CacheResponseDecorator(TestrailApi(DEFAULT_TESTRAIL_URL))
    testrail_client = TestrailClient(testrail_api)
    projects_count = len(testrail_client.get_projects())
    testrail_api.save(DEFAULT_CACHE_PATH)
    _logger.info("Cached %d projects in %.1f seconds", projects_count, time.monotonic() - started_at)


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
