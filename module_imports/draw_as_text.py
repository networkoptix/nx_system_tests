# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from module_imports._dependency import DependencyMap
from module_imports._dependency import DotLanguageRenderer

if __name__ == '__main__':
    dependency_map = DependencyMap(['mediaserver_api'])
    renderer = DotLanguageRenderer()
    dependency_map.draw_full(renderer)
    print(renderer.get_text())
