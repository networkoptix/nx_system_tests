# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from pathlib import Path

from module_imports._dependency import ModuleDependencyDiagramRenderer


class PyGraphvizRenderer(ModuleDependencyDiagramRenderer):

    def __init__(self):
        import pygraphviz
        self._graph = pygraphviz.AGraph(directed=True, rankdir='BT')

    def draw(self, image_filename: Path):
        self._graph.graph_attr.update({'dpi': '300', 'size': '15', 'ratio': '0.5'})
        self._graph.node_attr.update({'fontsize': '10'})
        image_format = image_filename.suffix.lstrip('.')
        self._graph.draw(image_filename, format=image_format, prog='dot')

    def add_module(self, node, label):
        self._graph.add_node(node, label=label)

    def add_dependency(self, edges):
        self._graph.add_edges_from(edges)

    def add_cluster(self, cluster_name, nodes):
        subgraph = self._graph.add_subgraph(nodes, f'cluster{cluster_name}')
        subgraph.graph_attr.update({'label': cluster_name})
