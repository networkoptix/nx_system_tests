# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from http.client import HTTPResponse
from typing import Any
from typing import Mapping
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.request import Request
from urllib.request import build_opener

from browser.webdriver import Browser
from browser.webdriver import WebDriverSession
from browser.webdriver import raise_webdriver_error


class ChromeDriverNotRunning(Exception):
    pass


class ChromeConfiguration:

    def __init__(self):
        self._capabilities = {
            'firstMatch': [{}],
            'alwaysMatch': {
                'browserName': 'chrome',
                'pageLoadStrategy': 'normal',
                'acceptInsecureCerts': True,
                # See: https://chromium.googlesource.com/chromium/src/+/master/chrome/test/chromedriver/capabilities.cc#1151
                'goog:loggingPrefs': {
                    # See: https://chromium.googlesource.com/chromium/src/+/refs/heads/main/chrome/test/chromedriver/logging.cc#179
                    # See: https://chromium.googlesource.com/chromium/src/+/main/chrome/test/chromedriver/logging.cc#55
                    'browser': 'ALL',
                    'driver': 'ALL',
                    'performance': 'ALL',
                    # 'devtools': 'ALL',  # TODO: Why cannot connect with this?
                    },
                'goog:chromeOptions': {
                    'prefs': {},
                    'extensions': [],
                    'args': [
                        '--no-sandbox',
                        ],
                    },
                },
            }

    def set_preference(self, key: str, value: str):
        chrome_preferences = self._capabilities['alwaysMatch']['goog:chromeOptions']['prefs']
        chrome_preferences[key] = value

    def as_json(self):
        return json.dumps({"capabilities": self._capabilities}).encode()


default_configuration = ChromeConfiguration()


def remote_chrome(
        webdriver_url: str, configuration: ChromeConfiguration = default_configuration) -> Browser:
    if not webdriver_url.startswith('http'):
        raise RuntimeError(f"Unsupported url scheme {webdriver_url}")
    _logger.info("%r: Requesting Chrome Session ID ...", webdriver_url)
    new_session_request = Request(
        url=webdriver_url + "/session", method="POST", data=configuration.as_json())
    new_session_request.add_header('Accept-Encoding', 'identity')
    new_session_request.add_header('Accept', 'application/json')
    new_session_request.add_header('Content-Type', 'application/json;charset=UTF-8')
    webdriver_opener = _WebdriverOpener()
    try:
        response_json = webdriver_opener.get_response(new_session_request)
    except URLError as err:
        if isinstance(err.reason, ConnectionRefusedError):
            raise ChromeDriverNotRunning(
                f"Connection to {webdriver_url} is refused. "
                "Check if ChromeDriver there is up and running")
        if isinstance(err.reason, BrokenPipeError):
            raise ChromeDriverNotRunning(
                f"Connection to {webdriver_url} is closed abruptly. "
                "Probably, ChromeDriver is not fully started, try again later")
        raise
    logging.info("%r: Received response data: %s", webdriver_url, response_json)
    capabilities = response_json['value']['capabilities']
    chrome_browser_version = _ChromeVersion(capabilities['browserVersion'])
    chrome_driver_version = _ChromeVersion(capabilities['chrome']['chromedriverVersion'])
    if not chrome_browser_version.is_compatible_with(chrome_driver_version):
        raise RuntimeError(
            f"ChromeDriver {chrome_driver_version} running on {webdriver_url} "
            f"does not match Chrome {chrome_browser_version}")
    session_id = response_json['value']['sessionId']
    _logger.info("Received Chrome Session ID: %s", session_id)
    session_url = webdriver_url + f'/session/{session_id}'
    session = _ChromeRemoteSession(webdriver_opener, session_url)
    _maximize_browser_window(session)
    return Browser(session)


def _maximize_browser_window(session: '_ChromeRemoteSession'):
    # The recommended way to start a browser window maximized is to put '--start-maximized'
    # to ChromeDriver options. However, it doesn't work while starting a browser inside 'xvfb-run'
    # without any windows manager running. POST to '/windows/maximize' works in both cases.
    # See: https://github.com/seleniumhq/selenium-google-code-issue-archive/issues/6775
    session.post("/window/maximize", {})


class _ChromeVersion:
    """Stores and processes Chrome version according to the given number.

    See: https://www.chromium.org/developers/version-numbers/
    """

    def __init__(self, version_string: str):
        [version, _, _git_info] = version_string.partition(' ')
        [self._major, self._minor, self._build, _patch] = version.split(".", maxsplit=4)
        self._repr = version_string

    def is_compatible_with(self, other: '_ChromeVersion') -> bool:
        if not isinstance(other, self.__class__):
            raise NotImplementedError(f"{other} is not an instance of {self.__class__}")
        # PATCH does not affect compatibility between Chrome and ChromeDriver
        my_version = (self._major, self._minor, self._build)
        other_version = (other._major, other._minor, other._build)
        return my_version == other_version

    def __repr__(self):
        return f'{self.__class__.__name__}({self._repr!r})'


class _WebdriverOpener:

    def __init__(self):
        self._opener = build_opener()

    def get_response(self, request: Request) -> Mapping[str, Any]:
        try:
            response: HTTPResponse = self._opener.open(request)
        except HTTPError as http_error:
            error_data = json.loads(http_error.read())
            _logger.debug(
                "%r: %s to %s returned a error: %s",
                self, request.method, request.full_url, error_data)
            raise_webdriver_error(error_data['value'])
        else:
            return json.loads(response.read())


class _ChromeRemoteSession(WebDriverSession):

    def __init__(self, opener: _WebdriverOpener, session_url: str):
        self._opener = opener
        self._session_url = session_url

    def post(self, path, json_data):
        body = json.dumps(json_data).encode()
        request = Request(url=self._session_url + path, method="POST", data=body)
        request.add_header('Accept-Encoding', 'identity')
        request.add_header('Accept', 'application/json')
        request.add_header('Content-Type', 'application/json;charset=UTF-8')
        _logger.debug("%r: POST request to %s: %s", self, path, json_data)
        response_json = self._opener.get_response(request)
        _logger.debug("%r: POST response: %s", self, response_json)
        return response_json['value']

    def get_json(self, path):
        request = Request(url=self._session_url + path, method="GET")
        _logger.debug("%r: GET request to: %s", self, path)
        response_json = self._opener.get_response(request)
        _logger.debug("%r: GET response: %s", self, response_json)
        return response_json['value']

    def delete(self, path, json_data):
        body = json.dumps(json_data).encode()
        request = Request(url=self._session_url + path, method="DELETE", data=body)
        request.add_header('Accept-Encoding', 'identity')
        request.add_header('Accept', 'application/json')
        request.add_header('Content-Type', 'application/json;charset=UTF-8')
        _logger.debug("%r: DELETE request to %s: %s", self, path, json_data)
        response_json = self._opener.get_response(request)
        _logger.debug("%r: DELETE response: %s", self, response_json)
        return response_json

    def __repr__(self):
        return f'<Chrome: {self._session_url} >'


_logger = logging.getLogger(__name__.split('.')[-1])
