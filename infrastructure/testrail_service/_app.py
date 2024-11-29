# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from functools import lru_cache
from functools import partial
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.parse import urlparse

from config import global_config
from distrib import DistribUrlBuildInfo
from infrastructure._http import App
from infrastructure._http import HTTPMethod
from infrastructure._http import StaticFilesHandler
from infrastructure._http import XSLTemplateHandler
from infrastructure.testrail_service._ft_job import select_ft_jobs
from infrastructure.testrail_service._report import VMSInfo
from infrastructure.testrail_service._report import form_reports
from infrastructure.testrail_service._send_reports import PostTestsMappingResult
from infrastructure.testrail_service._testrail_api import DEFAULT_TESTRAIL_URL
from infrastructure.testrail_service._testrail_api import TestrailApi
from infrastructure.testrail_service._testrail_api import TestrailClient
from infrastructure.testrail_service._testrail_cache import DEFAULT_CACHE_PATH
from infrastructure.testrail_service._testrail_cache import TestRailCache


def make_app():
    app_root = Path(__file__).parent
    testrail_api = TestrailApi(DEFAULT_TESTRAIL_URL)
    testrail_cache = TestRailCache(DEFAULT_CACHE_PATH)
    return partial(App, handlers=[
        StaticFilesHandler(app_root, relative_paths=[
            '/templates/main.css',
            '/templates/mapping.xsl',
            '/templates/projects_list.xsl',
            ]),
        _SelectTestrailProjectPage(testrail_cache),
        _PreviewTestsMapping(testrail_cache),
        PostTestsMappingResult(testrail_api),
        ])


class _SelectTestrailProjectPage(XSLTemplateHandler):
    _path = '/'
    _method = HTTPMethod.GET

    def __init__(self, testrail_cache: TestRailCache):
        super().__init__('/templates/projects_list.xsl')
        self._testrail_cache = testrail_cache

    def _handle(self, request: App):
        self._testrail_cache.refresh()
        testrail_client = TestrailClient(self._testrail_cache)
        rows = []
        for project in testrail_client.get_projects():
            for phase in project.list_phases():
                phase_preview_url = _PreviewTestsMapping.phase_url(
                    urlparse(request.path).query,
                    phase.id(),
                    )
                rows.append({
                    **project.present(),
                    **phase.present(phase_preview_url),
                    })
        self._send_template_data(request, {
            'header': {
                'title': 'TestRail Projects',
                'cache_age': self._testrail_cache.get_age(),
                },
            'rows': rows,
            })


class _PreviewTestsMapping(XSLTemplateHandler):
    _path = '/preview'
    _method = HTTPMethod.GET

    def __init__(self, testrail_cache: TestRailCache):
        super().__init__('/templates/mapping.xsl')
        self._testrail_cache = testrail_cache

    @classmethod
    def phase_url(cls, old_query, phase_id):
        query = {**dict(parse_qsl(old_query)), 'phase_id': phase_id}
        phase_mapping_preview_url = cls.url(*query.items())
        return phase_mapping_preview_url

    def _handle(self, request: App):
        try:
            batch_args = self._get_batch_args_from_request(request).values()
            [vms_url, *_] = batch_args
        except KeyError:
            request.send_response(
                HTTPStatus.FOUND, (
                    'Missing Batch arguments in query params. '
                    'Choose Batch from the main FT View page.'
                    ),
                )
            request.send_header('Location', global_config['ft_view_url'])
            request.end_headers()
            return
        parsed = parse_qs(urlparse(request.path).query)
        phase_id = parsed['phase_id'][0] if 'phase_id' in parsed else None
        if phase_id is None:
            request.send_response(HTTPStatus.BAD_REQUEST, "Missing phase_id param")
            request.end_headers()
            return
        jobs = select_ft_jobs(*batch_args)
        testrail_client = TestrailClient(self._testrail_cache)
        phase = testrail_client.find_project_phase(int(phase_id))
        runs = phase.list_runs()
        results = form_reports(jobs, runs, VMSInfo(vms_url, _make_vms_build(vms_url)))
        self._send_template_data(request, {
            'batch_url': self._make_batch_url_from_request(request),
            'reports_json': json.dumps(results['reports'], indent=4),
            **phase.present(),
            **results,
            })

    def _make_batch_url_from_request(self, request):
        params = self._get_batch_args_from_request(request)
        return global_config['ft_view_url'].rstrip('/') + '/?' + urlencode(params)

    @staticmethod
    def _get_batch_args_from_request(request: App):
        batch_args = {}
        for key in ('vms', 'revision', 'tag', 'machinery'):
            parsed = parse_qs(urlparse(request.path).query)
            value = parsed[key][0] if key in parsed else None
            if value is None:
                raise KeyError(f"Missing {key!r} param")
            batch_args[key] = value
        return batch_args


@lru_cache(16)
def _make_vms_build(vms_url: str):
    distrib_info = DistribUrlBuildInfo(vms_url)
    distrib_version = str(distrib_info.version())
    distrib_changeset = distrib_info.short_sha()
    return f'{distrib_version} ({distrib_changeset})'


_logger = logging.getLogger(__name__)
