# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

from pathlib import PurePosixPath
from pathlib import PureWindowsPath
from typing import Collection
from typing import Mapping
from typing import Optional


class Customization:

    def __init__(
            self,
            customization_name: str,
            installer_name: str,
            company_name: str,
            company_id: str,
            vms_id: str,
            vms_name: str,
            supported_languages: Collection[str],
            custom_mediaserver_application_name: Optional[str] = None,
            ):
        self.customization_name = customization_name
        self.installer_name = installer_name
        self.company_name = company_name
        self.company_id = company_id
        self._vms_id = vms_id
        self._vms_name = vms_name
        self.supported_languages = supported_languages
        self._custom_mediaserver_application_name = custom_mediaserver_application_name

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.customization_name}>"

    @property
    def storage_dir_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/cmake/properties.cmake#L36
        return self._vms_id + ' Media'

    @property
    def windows_client_executable(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/cmake/properties.cmake#L68
        return self._vms_id

    @property
    def windows_server_installation_subdir(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/wix/server/server_feature.wxs#L8
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/wix/server/server_product.wxs#L235
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/cmake/properties.cmake#L26
        return PureWindowsPath(self.company_name, self._vms_name, 'MediaServer')

    @property
    def windows_server_registry_key(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/wix/server/CMakeLists.txt#L5
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/cmake/properties.cmake#L51
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/wix/server/server_feature.wxs#L74
        return f'HKEY_LOCAL_MACHINE\\SOFTWARE\\{self.company_name}\\{self._mediaserver_application_name}'

    @property
    def windows_server_service_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/wix/server/server_feature.wxs#L22
        return self.customization_name + 'MediaServer'

    @property
    def windows_server_app_data_subdir(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/wix/server/server_product.wxs#L164
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/wix/server/server_product.wxs#L128
        return PureWindowsPath(self.company_name, self._mediaserver_application_name)

    @property
    def windows_client_installation_subdir(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/vms/distribution/wix/desktop_client/client_feature.wxs#L42
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/vms/distribution/wix/desktop_client/client_product.wxs#L161
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/cmake/properties.cmake#L26
        # Plus the full version.
        return PureWindowsPath(self.company_name, self._vms_name, 'Client')

    @property
    def windows_client_registry_key(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/vms/distribution/wix/desktop_client/CMakeLists.txt#L9
        return f'HKEY_CURRENT_USER\\SOFTWARE\\{self.company_name}\\{self._client_internal_name}'

    @property
    def windows_server_display_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/wix/server/server_product.wxs#L6
        return self._vms_name + ' Server'

    @property
    def windows_client_display_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/vms/distribution/wix/desktop_client/client_product.wxs#L6
        return self._vms_name + ' Client'

    @property
    def windows_bundle_display_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/wix/bundle/combined_bundle.wxs#L7
        return self._vms_name + ' Bundle'

    @property
    def linux_server_subdir(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/deb/mediaserver/CMakeLists.txt#L28
        return PurePosixPath(self.company_id, 'mediaserver')

    @property
    def linux_user(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/deb/mediaserver/CMakeLists.txt#L36
        return self.company_id

    @property
    def linux_server_package_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/vms/distribution/deb/client/deb_files.in/debian/control.template
        # See: https://www.debian.org/doc/debian-policy/ch-controlfields.html
        return self.company_id + '-mediaserver'

    @property
    def linux_server_service_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/deb/mediaserver/CMakeLists.txt#L30
        return self.company_id + '-mediaserver'

    @property
    def linux_root_tool_service_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/distribution/deb/mediaserver/CMakeLists.txt#L30
        return self.company_id + '-root-tool'

    @property
    def linux_client_package_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/vms/distribution/deb/client/deb_files.in/debian/control.template
        # See: https://www.debian.org/doc/debian-policy/ch-controlfields.html
        return self.company_id + '-client'

    @property
    def linux_client_subdir(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/cmake/properties.cmake#L87
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/vms/distribution/deb/client/build_distribution.sh#L16
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/vms/distribution/deb/client/build_distribution.conf.in#L3
        return PurePosixPath(self.company_id, 'client')

    @property
    def linux_client_data_dir(self):
        return PurePosixPath('/root/.local/share', self.company_name, self._client_internal_name)

    @property
    def linux_client_config_path(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/cmake/properties.cmake#L35
        return PurePosixPath(self.company_name, self._client_internal_name + '.conf')

    @property
    def _client_internal_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/cmake/properties.cmake#L35
        return self.company_name + ' ' + self._vms_id + ' Client'

    @property
    def _mediaserver_application_name(self):
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/open/cmake/properties.cmake#L51
        if self._custom_mediaserver_application_name is not None:
            return self._custom_mediaserver_application_name
        return self.company_name + ' Media Server'


# See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/618201109/Translations+by+customization
_all_supported_languages = [
    'cs_CZ',
    'de_DE',
    'en_US',
    'en_GB',
    'es_ES',
    'fi_FI',
    'fr_FR',
    'he_IL',
    'hu_HU',
    'it_IT',
    'ja_JP',
    'ko_KR',
    'nl_BE',
    'nl_NL',
    'no_NO',
    'pl_PL',
    'pt_BR',
    'pt_PT',
    'ru_RU',
    'sv_SE',
    'th_TH',
    'tr_TR',
    'uk_UA',
    'vi_VN',
    'zh_CN',
    'zh_TW',
    ]


known_customizations: Mapping[str, Customization] = {
    'hanwha': Customization(
        customization_name='hanwha',
        installer_name='wave',
        company_name='Hanwha',
        company_id='hanwha',
        vms_id='Wisenet WAVE',
        vms_name='Wisenet WAVE',
        supported_languages=_all_supported_languages,
        ),
    'default': Customization(
        customization_name='default',
        installer_name='nxwitness',
        company_name='Network Optix',
        company_id='networkoptix',
        vms_id='HD Witness',
        vms_name='Nx Witness',
        supported_languages=_all_supported_languages,
        ),
    'metavms': Customization(
        customization_name='metavms',
        installer_name='metavms',
        company_name='Network Optix',
        company_id='networkoptix-metavms',
        vms_id='Nx MetaVMS',
        vms_name='Nx Meta',
        custom_mediaserver_application_name='Network Optix MetaVMS Media Server',
        supported_languages=_all_supported_languages,
        ),
    'digitalwatchdog': Customization(
        customization_name='digitalwatchdog',
        installer_name='dwspectrum',
        company_name='Digital Watchdog',
        company_id='digitalwatchdog',
        vms_id='DW Spectrum',
        vms_name='DW Spectrum',
        supported_languages=['en_US', 'fr_FR', 'es_ES'],
        ),
    }
