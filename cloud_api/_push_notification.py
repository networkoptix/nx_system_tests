# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import re
import time
from collections import deque
from contextlib import contextmanager
from html.parser import HTMLParser
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Set
from urllib.parse import urljoin
from uuid import UUID
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import ElementTree

from requests import HTTPError
from requests.models import Response
from requests.sessions import Session

_logger = logging.getLogger(__name__)


class CloudPushNotificationsViewer:

    def __init__(self, cloud_host: str, email: str, password: str):
        self._email = email
        self._password = password
        self._base_url = f'https://{cloud_host}/'
        self._notifications_url = urljoin(self._base_url, 'admin/notifications/pushnotification/')
        self._session = Session()
        self._new_notifications = []
        self._log_in()

    def can_view_push_notifications(self) -> bool:
        try:
            response = self._request('GET', self._notifications_url)
        except HTTPError as e:
            if e.response.status_code == 403:
                # Can open the admin panel but does not have permission to view push notifications.
                return False
            raise
        if response.url != self._notifications_url:
            # Can't open admin panel - redirected to main page.
            return False
        return True

    @property
    def new_notifications(self) -> tuple:
        return tuple(self._new_notifications)

    def _request(self, method: str, url: str, **kwargs) -> Response:
        kwargs = {'timeout': 30, **kwargs}
        response = self._session.request(method, url, **kwargs)
        if 400 <= response.status_code < 600:
            try:
                error = response.json()
            except ValueError:
                raise HTTPError(str(response.status_code), response=response)
            if 'errorText' in error:
                raise RuntimeError(
                    f"Request {method} {url} failed: HTTP {response.status_code}; "
                    f"error: {error['errorText']}")
            raise RuntimeError(
                f"Request {method} {url} failed: HTTP {response.status_code}; "
                f"additional information: {error}")
        return response

    def _get_content(self, url: str, **kwargs) -> str:
        response = self._request('GET', url, **kwargs)
        return response.text

    def _log_in(self):
        self._request(
            'POST',
            self._base_url + 'api/account/login',
            json={
                'email': self._email,
                'password': self._password,
                },
            )

    @staticmethod
    def _get_notification_id(notification_url: str) -> int:
        match = re.search(r'/(?P<id>\d+)/change/', notification_url)
        notification_id = match.group('id')
        return int(notification_id)

    @staticmethod
    def _find_single_element(root_element: Element, xpath_search_pattern: str) -> Element:
        elements = root_element.findall(xpath_search_pattern)
        if not elements:
            raise RuntimeError(
                f"No elements with xpath {xpath_search_pattern} found inside "
                f"{root_element}")
        try:
            [element] = elements
        except ValueError:
            raise RuntimeError(
                f"Multiple elements with xpath {xpath_search_pattern} found inside "
                f"{root_element.tag}, expected only one")
        return element

    def _get_notification(self, notification_url: str) -> '_PushNotification':
        notification = self._get_content(notification_url)
        _logger.debug("Notification info:\n%r", notification)
        parsed_content = _parse_html(notification)
        notification_form = self._find_single_element(
            parsed_content, '//*[@id="pushnotification_form"]')  # noqa SpellCheckingInspection
        parsed_notification_data = {}
        for field in _PushNotification._fields:
            if field == 'id':
                continue  # ID is obtained from URL.
            element = self._find_single_element(
                notification_form, f'.//*[@class="form-row field-{field}"]')
            element_info = self._find_single_element(element, './/*[@class="readonly"]')
            parsed_notification_data[field] = element_info.text
        return _PushNotification(
            title=parsed_notification_data['title'],
            body=parsed_notification_data['body'],
            raw_targets=json.loads(parsed_notification_data['raw_targets']),
            raw_system_id=UUID(parsed_notification_data['raw_system_id']),
            id=self._get_notification_id(notification_url),
            )

    def _get_notification_urls(self, cloud_system_id: UUID) -> Set[str]:
        notifications_url = f'{self._notifications_url}?raw_system_id__exact={cloud_system_id}'
        # If requested page not found - cloud will send redirect to first page. Forbid redirects
        # so this situation will raise an error.
        notification_list = self._get_content(notifications_url)
        _logger.debug("Notification list:\n%r", notification_list)
        parsed_content = _parse_html(notification_list)
        link_elements = parsed_content.findall(
            '//table[@id="result_list"]/tbody/tr/th[@class="field-short_title"]/a')
        relative_urls = [element.attrib['href'] for element in link_elements]
        return {urljoin(self._base_url, url) for url in relative_urls}

    @contextmanager
    def wait_for_new_notifications(
            self,
            cloud_system_id: UUID,
            timeout_sec: float = 10,
            expected_notification_count: int = 1,
            ):
        # There is pagination enabled on cloud notification page - 110 notifications per page.
        # To simplify function logic expected notification count is limited to 110 notifications.
        # If a need arises to expect more than 110 notifications in one wait - this function
        # should be reworked.
        # There is a way to get all notifications at once, but it is possible that fetching
        # too many notification at once will be very slow and unreliable.
        # It is more safe to load one page at a time.
        #
        # To avoid notification clashes in parallel test runs cloud_system_id is used to filter out
        # notifications, related to current cloud system.
        notifications_per_page = 110
        if expected_notification_count > notifications_per_page:
            raise RuntimeError("Too many notifications expected. Method rework is needed.")
        self._new_notifications = []
        old_notification_urls = self._get_notification_urls(cloud_system_id)
        yield
        urls_already_checked = set()
        parsed_notifications = []
        started = time.monotonic()
        while time.monotonic() - started < timeout_sec:
            notification_urls = self._get_notification_urls(cloud_system_id)
            urls_to_skip = {*old_notification_urls, *urls_already_checked}
            new_notification_urls = notification_urls - urls_to_skip
            ordered_new_urls = sorted(list(new_notification_urls), reverse=True)
            for url in ordered_new_urls:
                urls_already_checked.update([url])
                notification = self._get_notification(url)
                if cloud_system_id != notification.raw_system_id:
                    raise RuntimeError(
                        f"Notification {notification.raw_system_id} does not belong "
                        f"to the cloud system {cloud_system_id}")
                parsed_notifications.insert(0, notification)  # Preserve URL order.
            target_notification_count = len(parsed_notifications)
            if target_notification_count < expected_notification_count:
                time.sleep(1)
                continue
            unique_notification_ids = {n.id for n in parsed_notifications}
            if target_notification_count > len(unique_notification_ids):
                raise RuntimeError(
                    f"The same notifications received more than once: {parsed_notifications}")
            if target_notification_count > expected_notification_count:
                raise _TooManyNotificationsError(target_notification_count, (
                    f"Received {target_notification_count} notifications from {cloud_system_id}; "
                    f"expected {expected_notification_count}; "
                    f"notifications: {parsed_notifications}"))
            self._new_notifications = parsed_notifications
            break
        else:
            if parsed_notifications:
                raise RuntimeError(
                    f"Received less notifications for {cloud_system_id} than expected "
                    f"after {timeout_sec} seconds: "
                    f"received {len(parsed_notifications)}; "
                    f"expected {expected_notification_count}; "
                    f"notifications: {parsed_notifications}")
            raise _NoNotificationsError(
                "Cloud did not receive any notifications for "
                f"{cloud_system_id} in {timeout_sec} seconds. "
                "Probably caused by a change in the HTML format of the notifications page")

    @contextmanager
    def ensure_no_notifications_received(self, cloud_system_id: UUID, silence_period_sec: float):
        try:
            with self.wait_for_new_notifications(
                    cloud_system_id,
                    timeout_sec=silence_period_sec,
                    expected_notification_count=1):
                yield
        except _NoNotificationsError:
            pass
        except _TooManyNotificationsError as e:
            raise RuntimeError(
                f"Received {e.notification_count} notifications for {cloud_system_id} "
                f"in {silence_period_sec} seconds, expected none.")
        else:
            [notification] = self.new_notifications
            raise RuntimeError(
                f"Received one notification {notification} for {cloud_system_id} "
                f"in {silence_period_sec} seconds, expected none.")


class _PushNotification(NamedTuple):
    title: str
    body: str
    raw_targets: str
    raw_system_id: UUID
    id: int


class _NoNotificationsError(Exception):
    pass


class _TooManyNotificationsError(Exception):

    def __init__(self, notification_count: int, message: str):
        super().__init__(message)
        self.notification_count = notification_count


def _parse_html(content: str) -> ElementTree:
    parser = _CloudHTMLParser()
    parser.feed(content)
    return parser.root


class _CloudHTMLParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.root = ElementTree()
        self._elements_stack: deque[Element] = deque()
        self._element_opened = False

    def _get_current_element(self) -> Optional[Element]:
        try:
            return self._elements_stack[-1]
        except IndexError:
            return None

    def handle_data(self, data: str):
        current_element = self._get_current_element()
        if current_element is None:
            return
        if self._element_opened:
            current_element.text += data
        else:
            current_element.tail += data

    def handle_startendtag(self, tag: str, attrs: Sequence[tuple[str, str]]):
        new_element = _make_normalized_element(tag, attrs)
        current_element = self._get_current_element()
        current_element.append(new_element)

    def _set_as_root(self, element: Element):
        # See: https://docs.python.org/3/library/xml.etree.elementtree.html?highlight=etree#xml.etree.ElementTree.ElementTree._setroot
        # noinspection PyUnresolvedReferences
        # noinspection PyProtectedMember
        self.root._setroot(element)
        self._elements_stack.append(element)

    def handle_starttag(self, tag: str, attrs: Sequence[tuple[str, str]]):
        if _is_format(tag):
            return
        new_element = _make_normalized_element(tag, attrs)
        current_element = self._get_current_element()
        if current_element is None:
            self._set_as_root(new_element)
            return
        current_element.append(new_element)
        if not _is_void(tag):
            self._element_opened = True
            self._elements_stack.append(new_element)

    def handle_endtag(self, tag: str):
        if _is_format(tag):
            return
        top_element = self._elements_stack.pop()
        if top_element.tag != tag:
            raise RuntimeError(
                f"Closing tags mismatch. Received {tag}, but top of"
                f"the elements stack is {top_element}")
        self._element_opened = False


def _is_void(tag: str) -> bool:
    # See: https://www.w3.org/TR/2011/WD-html-markup-20110113/syntax.html#void-elements
    return tag in {
        'area', 'base', 'br', 'col', 'command', 'embed', 'hr', 'img', 'input',
        'keygen', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


def _is_format(tag: str) -> bool:
    # See: https://www.w3schools.com/html/html_formatting.asp
    return tag in {'b', 'em', 'i', 'small', 'strong', 'sub', 'sup', 'ins', 'del', 'mark'}


def _make_normalized_element(tag: str, attrs: Sequence[tuple[str, str]]) -> Element:
    element = Element(tag, dict(attrs))
    element.text = element.tail = ''
    return element
