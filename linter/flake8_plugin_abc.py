# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from ast import ClassDef
from ast import Module
from ast import Name
from ast import walk


def no_abc_superclass(tree: Module):
    """There must be one way to define an abstract class. Prefer ABCMeta.

    PyCharm chooses this for automated refactorings. It does not pollute MRO.
    ABC is not a true base class. But metaclass=ABCMeta is a bit longer.
    """
    for node in walk(tree):
        if isinstance(node, ClassDef):
            for b in node.bases:
                if isinstance(b, Name):  # It can be a generic
                    if b.id == 'ABC':  # Assume it's abc.ABC
                        yield (
                            b.lineno, b.col_offset,
                            "X026 Abstract classes must be defined with metaclass=ABCMeta",
                            None)
