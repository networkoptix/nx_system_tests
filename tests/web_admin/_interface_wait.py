# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import concurrent.futures
import logging
from typing import Any
from typing import Callable

from browser.webdriver import ElementNotFound


def element_is_present(raises_element_not_found: Callable[[], Any]) -> bool:
    try:
        raises_element_not_found()
    except ElementNotFound:
        return False
    return True


def assert_elements_absence(*return_element_callables: Callable[[], Any]):
    # WebAdmin interface is a JavaScript driven application what means that nearly all the
    # HTML code is generated in runtime by multiple scripts running in parallel.
    # That style of WEB programming imposes certain limitations:
    # - There is no point after that a freshly opened page may be considered "fully loaded".
    # There are always some scripts running in the background and updating the page.
    # - Load order of elements is not guaranteed because different page parts may be populated
    # by different scripts.
    # - Parent elements after their appearance may not contain all the child elements because
    # elements are populated in runtime.
    # Thus, the only definite way to ensure that elements are not displayed in the page, is to
    # wait every element independently of each other. Unfortunately, when there are many elements
    # to check, the overall wait time is intolerable long.
    if len(return_element_callables) == 1:
        raise ValueError(
            "This function should be use to wait multiple elements absence. "
            "Single elements absence should be waited explicitly")
    max_workers = min(_maximum_workers_threshold, len(return_element_callables))
    found_elements = []
    with concurrent.futures.ThreadPoolExecutor(max_workers) as pool:
        futures = {}
        for returning_element_callable in return_element_callables:
            future = pool.submit(returning_element_callable)
            futures[future] = returning_element_callable
        for future in concurrent.futures.as_completed(futures.keys()):
            callable_name = futures[future]
            try:
                element = future.result()
            except ElementNotFound:
                _logger.info("%s is not found", callable_name)
            else:
                _logger.info("%s has returned %s", callable_name, element)
                found_elements.append(callable_name)
    if found_elements:
        raise AssertionError(f"Elements found: {found_elements}")


# Value protects a WebDriver process from being overloaded with parallel requests.
_maximum_workers_threshold = 8

_logger = logging.getLogger(__name__.split('.')[-1])
