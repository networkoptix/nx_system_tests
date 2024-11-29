# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import setuptools

setuptools.setup(
    name='nx-software-cameras',
    version='0.0.4',
    python_requires='>=3.8',
    install_requires=['Pillow>=8.1.0'],
    package_dir={'software_cameras': ''},
    packages=['software_cameras'],
    )
