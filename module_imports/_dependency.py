# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import ast
import importlib
import re
import sys
from abc import ABCMeta
from abc import abstractmethod
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Collection
from typing import Iterable
from typing import Mapping
from typing import Optional
from typing import Tuple


class DependencyMap:

    def __init__(self, root_modules: Collection[str]):
        self._root_modules = root_modules
        for m in root_modules:
            importlib.import_module(m)
        modules = [_ImportedModule(m) for m in root_modules]
        self._map = {}
        while True:
            try:
                module = modules.pop(0)
            except IndexError:
                break
            if module.name in self._map:
                continue
            module_dependencies = [
                dependency
                for dependency in module.list_dependencies()
                if dependency.is_first_party()
                ]
            self._map[module.name] = [dependency.name for dependency in module_dependencies]
            modules.extend([
                dependency
                for dependency in module_dependencies
                if dependency.name not in self._map
                ])

    def draw_full(self, renderer: 'ModuleDependencyDiagramRenderer'):
        clusters = self._clusters()
        full_map = self._full()
        _make_graph(
            renderer,
            full_map,
            node_clusters=clusters,
            node_labels={k: shrink_module_name(k) for k in full_map},
            )

    def draw_contracted(self, renderer: 'ModuleDependencyDiagramRenderer'):
        contracted_map = self._contracted()
        _make_graph(
            renderer,
            contracted_map,
            node_labels={k: shrink_module_name(k) for k in contracted_map},
            )

    def _full(self) -> Mapping[str, Collection[str]]:
        return {**self._map}

    def _clusters(self) -> Mapping[str, Collection[str]]:
        result = {}
        for module in self._map.keys():
            parts = module.split('.')
            if parts[0] == 'framework':
                cluster = '.'.join(parts[:2])
            else:
                cluster = parts[0]
            result.setdefault(cluster, []).append(module)
        return result

    def _contracted(self) -> Mapping[str, Collection[str]]:
        module_cluster = {
            node: cluster
            for cluster, nodes in self._clusters().items()
            for node in nodes
            }
        result = {}
        for module_name, dependencies in self._map.items():
            if module_name not in self._root_modules:
                node_name = module_cluster[module_name]
            else:
                node_name = module_name
            clustered_dependencies = result.setdefault(node_name, [])
            for dependency in dependencies:
                clustered_dependency = module_cluster[dependency]
                if node_name == clustered_dependency:
                    continue
                if clustered_dependency in clustered_dependencies:
                    continue
                clustered_dependencies.append(clustered_dependency)
        return result


def _make_graph(
        renderer: 'ModuleDependencyDiagramRenderer',
        graph_raw: Mapping[str, Collection[str]],
        node_clusters: Mapping[str, Collection[str]] = MappingProxyType({}),
        node_labels: Mapping[str, str] = MappingProxyType({}),
        ):
    for node in graph_raw.keys():
        renderer.add_module(node, node_labels.get(node, node))
    edges = [
        (source, destination)
        for source, neighbors in graph_raw.items()
        for destination in neighbors
        ]
    renderer.add_dependency(edges)
    for cluster_name, nodes in node_clusters.items():
        if len(nodes) == 1:
            continue
        renderer.add_cluster(cluster_name, nodes)


class ModuleDependencyDiagramRenderer(metaclass=ABCMeta):

    @abstractmethod
    def add_module(self, node, label):
        pass

    @abstractmethod
    def add_dependency(self, edges):
        pass

    @abstractmethod
    def add_cluster(self, cluster_name, nodes):
        pass


class DotLanguageRenderer(ModuleDependencyDiagramRenderer):

    def __init__(self):
        self._result = 'digraph {\n'

    def get_text(self) -> str:
        return self._result + '}\n'

    def add_module(self, node: str, label: str):
        self._result += f'  {self._quote(node)} [label={self._quote(label)}];\n'

    def add_dependency(self, edges: Iterable[Tuple[str, str]]):
        for u, v in edges:
            self._result += f'  {self._quote(u)} -> {self._quote(v)};\n'

    def add_cluster(self, cluster_name: str, nodes: Iterable[str]):
        self._result += '  subgraph ' f'{self._quote(cluster_name)}' ' {\n'
        for v in nodes:
            self._result += f'    {self._quote(v)};\n'
        self._result += '  };\n'

    @staticmethod
    def _quote(v):
        # See: https://graphviz.org/doc/info/lang.html
        if re.fullmatch(r'\w+', v):
            return v
        return '"' + v.replace('"', r'\"') + '"'


def shrink_module_name(module_name: str) -> str:
    parts = module_name.split('.')
    return '.'.join([*[p[0] for p in parts[:-1]], parts[-1]])


class _ImportedModule:

    def __init__(self, module_name: str):
        if module_name not in sys.modules:
            raise _NotImported(f"Module {module_name!r} is not imported")
        self.name = module_name
        self._module = sys.modules[module_name]

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.name == other.name

    def __hash__(self):
        return hash(self.__class__.__name__ + self.name)

    def is_first_party(self) -> bool:
        try:
            source_path = self._get_source_path()
        except _SourcePathMissing:
            return False
        if _get_project_root() not in source_path.parents:
            return False
        if _get_nested_venv_root() in source_path.parents:
            return False
        return True

    def list_dependencies(self) -> Collection['_ImportedModule']:
        result = []
        source_path = self._get_source_path()
        relative_source_path = source_path.relative_to(_get_project_root())
        module_source_text = source_path.read_text()
        for ast_node in ast.walk(ast.parse(module_source_text)):
            if isinstance(ast_node, ast.Import):
                modules = _Import(ast_node).modules()
            elif isinstance(ast_node, ast.ImportFrom):
                if ast_node.level == 0:
                    modules = _AbsoluteImportFrom(ast_node).modules()
                else:
                    modules = _RelativeImportFrom(ast_node, relative_source_path).modules()
            else:
                continue
            for module in modules:
                if module not in result:
                    result.append(module)
        return result

    @lru_cache(1)
    def _get_source_path(self) -> Path:
        try:
            spec = self._module.__spec__
        except AttributeError:
            raise _SourcePathMissing('__spec__ attribute is absent')
        if spec is None:
            raise _SourcePathMissing('__spec__ is None')
        if spec.origin is None:
            raise _SourcePathMissing('__spec__.origin is None')
        if spec.origin == 'built-in':
            raise _SourcePathMissing('__spec__.origin is "built-in"')
        if spec.origin == 'frozen':
            raise _SourcePathMissing('__spec__.origin is "frozen"')
        return Path(spec.origin)


class _ImportStatement(metaclass=ABCMeta):

    def modules(self) -> Collection['_ImportedModule']:
        result = []
        for name in self._possible_module_names():
            try:
                result.append(_ImportedModule(name))
            except _NotImported:
                continue
        return result

    @abstractmethod
    def _possible_module_names(self) -> Collection[str]:
        pass


class _Import(_ImportStatement):

    def __init__(self, ast_node: ast.Import):
        self._node = ast_node

    def _possible_module_names(self):
        return [alias.name for alias in self._node.names]


class _AbsoluteImportFrom(_ImportStatement):

    def __init__(self, ast_node: ast.ImportFrom):
        if ast_node.level != 0:
            raise RuntimeError(f'{ast_node} is not an absolute import from statement')
        self._node = ast_node

    def _possible_module_names(self):
        module_name = self._node.module
        if module_name is None:
            raise RuntimeError(
                f"Module name is None on absolute import from statement {self._node!r}")
        return [
            module_name,
            *[module_name + '.' + alias.name for alias in self._node.names],
            ]


class _RelativeImportFrom(_ImportStatement):

    def __init__(self, ast_node: ast.ImportFrom, relative_module_path: Path):
        if ast_node.level == 0:
            raise RuntimeError(f'{ast_node} is not a relative import from statement')
        self._node = ast_node
        self._current_module_parts = relative_module_path.parts

    def _possible_module_names(self):
        level = self._node.level
        package_parts = self._current_module_parts[:-level]
        if self._node.module is None:
            module_name = '.'.join(package_parts)
        else:
            module_name = '.'.join([*package_parts, self._node.module])
        return [
            module_name,
            *[module_name + '.' + alias.name for alias in self._node.names],
            ]


@lru_cache(1)
def _get_project_root() -> Path:
    root = Path(__file__).parent.parent
    assert str(root) in sys.path
    return root


@lru_cache(1)
def _get_nested_venv_root() -> Optional[Path]:
    executable = Path(sys.executable)
    if _get_project_root() in executable.parents:
        return executable.parent.parent
    return None


class _SourcePathMissing(Exception):
    pass


class _NotImported(Exception):
    pass
