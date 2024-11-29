# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Everything for distrib/ dirs, installer names and metadata files.

This component must not depend on any local or third-party libs,
except the Python Standard Library.
"""
from distrib._build_info import BuildInfo
from distrib._build_info import BuildInfoError
from distrib._build_info import BuildInfoNotFound
from distrib._build_info import DistribUrlBuildInfo
from distrib._build_info import PathBuildInfo
from distrib._build_info import RawBytesBuildInfo
from distrib._build_registry import BuildRecord
from distrib._build_registry import BuildRegistry
from distrib._customizations import Customization
from distrib._customizations import known_customizations
from distrib._distrib import APINotSupported
from distrib._distrib import BranchNotSupported
from distrib._distrib import Distrib
from distrib._distrib import OSNotSupported
from distrib._distrib import SpecificFeatureNotSupported
from distrib._distrib import UpdatesNotSupported
from distrib._installer_name import InstallerArch
from distrib._installer_name import InstallerComponent
from distrib._installer_name import InstallerKey
from distrib._installer_name import InstallerName
from distrib._installer_name import InstallerOs
from distrib._installer_name import LINUX_BENCHMARK
from distrib._installer_name import LINUX_CLIENT
from distrib._installer_name import LINUX_SERVER
from distrib._installer_name import LINUX_SERVER_ARM32
from distrib._installer_name import LINUX_SERVER_ARM64
from distrib._installer_name import MACOS_SERVER_ARM64
from distrib._installer_name import PackageNameParseError
from distrib._installer_name import WINDOWS_BENCHMARK
from distrib._installer_name import WINDOWS_BUNDLE
from distrib._installer_name import WINDOWS_CLIENT
from distrib._installer_name import WINDOWS_SERVER
from distrib._installer_set import InstallerNotFound
from distrib._installer_set import InstallerSet
from distrib._installers_url import list_distrib_files
from distrib._installers_url import list_installers_url
from distrib._specific_features import SpecificFeatures
from distrib._version import Version

__all__ = [
    'APINotSupported',
    'BranchNotSupported',
    'BuildInfo',
    'BuildInfoError',
    'BuildInfoNotFound',
    'BuildRecord',
    'BuildRegistry',
    'Customization',
    'Distrib',
    'DistribUrlBuildInfo',
    'InstallerArch',
    'InstallerComponent',
    'InstallerKey',
    'InstallerName',
    'InstallerNotFound',
    'InstallerOs',
    'InstallerSet',
    'LINUX_BENCHMARK',
    'LINUX_CLIENT',
    'LINUX_SERVER',
    'LINUX_SERVER_ARM32',
    'LINUX_SERVER_ARM64',
    'MACOS_SERVER_ARM64',
    'OSNotSupported',
    'PackageNameParseError',
    'PathBuildInfo',
    'RawBytesBuildInfo',
    'SpecificFeatureNotSupported',
    'SpecificFeatures',
    'UpdatesNotSupported',
    'Version',
    'WINDOWS_BENCHMARK',
    'WINDOWS_BUNDLE',
    'WINDOWS_CLIENT',
    'WINDOWS_SERVER',
    'known_customizations',
    'list_distrib_files',
    'list_installers_url',
    ]
