# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from pathlib import Path

from cloud_api._push_notification import _parse_html

_cwd = Path(__file__).parent
_notification_url_text = (_cwd / 'notification_url.html').read_text('utf-8')
_notification_list_text = (_cwd / 'notification_list.html').read_text('utf-8')


def test_parse_notification_url():
    search_pattern = '//*[@id="pushnotification_form"]'
    root_tree = _parse_html(_notification_url_text)
    [result] = root_tree.findall(search_pattern)
    assert result.attrib['id'] == 'pushnotification_form'


def test_parse_notification_list():
    search_pattern = '//table[@id="result_list"]/tbody/tr/th[@class="field-short_title"]/a'
    root_tree = _parse_html(_notification_list_text)
    [result] = root_tree.findall(search_pattern)
    expected = "/admin/notifications/pushnotification/36642/change/?_changelist_filters=raw_system_id__exact%3D241a54b8-8cb5-4965-8fa1-15b1862bf76e"
    assert result.attrib['href'] == expected
