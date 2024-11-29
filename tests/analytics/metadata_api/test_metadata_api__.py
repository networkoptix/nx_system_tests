# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
from contextlib import ExitStack
from pathlib import Path
from typing import Optional

from mediaserver_api.analytics import AnalyticsEngineSettings
from tests.analytics.common import compare_settings_dicts
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.metadata_api.integration import MetadataApiIntegration


def _test_metadata_api(
        distrib_url: str,
        vm_type: str,
        api_version: str,
        exit_stack: ExitStack,
        with_plugins_from_release: Optional[str] = None,
        ):
    stand = prepare_one_mediaserver_stand(
        distrib_url, vm_type, api_version, exit_stack, with_plugins_from_release)
    mediaserver = stand.mediaserver()
    integration_manifest_file = Path(__file__).parent / 'test_data' / 'integration_manifest.json'
    engine_manifest_file = Path(__file__).parent / 'test_data' / 'engine_manifest.json'
    integration_manifest = json.loads(integration_manifest_file.read_text())
    integration_request = mediaserver.api.create_integration_request(
        integration_manifest=integration_manifest,
        engine_manifest=json.loads(engine_manifest_file.read_text()),
        pin_code='5555',
        )
    mediaserver.api.approve_integration_request(integration_request.id)
    integration_user_api = mediaserver.api.with_digest_auth(
        *integration_request.get_user_credentials())
    integration = exit_stack.enter_context(MetadataApiIntegration(integration_user_api))
    integration.connect()
    integration_user = integration_user_api.get_user(integration_request.id)
    integration_request_data = integration_user.get_integration_request_data()
    if integration_request_data is None:
        raise RuntimeError(f"Integration request data was not found for {integration_user!r}")
    engine_id = integration_request_data['engineId']
    engine_settings = mediaserver.api.get_analytics_engine_settings(engine_id)
    engine_settings_model_errors = [
        compare_settings_dicts(engine_settings_model_item, manifest_settings_model_item)
        for (engine_settings_model_item, manifest_settings_model_item)
        in zip(engine_settings.model['items'], integration_manifest['engineSettingsModel']['items'])]
    assert not any(engine_settings_model_errors), (
        f"Engine settings model errors: {engine_settings_model_errors}")
    engine_active_settings_subscription = integration.subscribe_to_engine_active_settings_change()
    mediaserver.api.notify_engine_active_setting_changed(
        engine_id=engine_id,
        engine_settings=engine_settings,
        setting_name='ActiveCheckBox',
        new_setting_value=True,
        )
    new_engine_settings = AnalyticsEngineSettings(
        engine_active_settings_subscription.get().params['parameters'])
    assert new_engine_settings.values['ActiveCheckBox']
