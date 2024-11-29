# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from pathlib import Path
from typing import Sequence

from module_imports._dependency import DependencyMap
from module_imports._graph import PyGraphvizRenderer


def main(argv: Sequence[str]):
    root_modules = (
        argv if argv else
        ['mediaserver_api', 'os_access', 'installation'])
    dependency_map = DependencyMap(root_modules)
    renderer = PyGraphvizRenderer()
    dependency_map.draw_full(renderer)
    path = Path('full.png').absolute()
    print(path)
    renderer.draw(path)
    renderer = PyGraphvizRenderer()
    dependency_map.draw_contracted(renderer)
    path = Path('contracted.png').absolute()
    print(path)
    renderer.draw(path)


if __name__ == '__main__':
    main(sys.argv[1:])
