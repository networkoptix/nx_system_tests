# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import ast
import fnmatch
import logging
import os
import shutil
import subprocess
import sys
import textwrap
from contextlib import contextmanager
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Container
from typing import Mapping
from typing import Optional
from typing import TextIO
from xml.sax.saxutils import XMLGenerator

from _internal.service_registry import gitlab_ft_ft
from directories import make_artifact_store

_root = Path(__file__).parent.parent
assert str(_root) in sys.path


def main():
    if os.getenv('DRY_RUN'):
        return 0
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    out_file = Path(f'~/.cache/nxft-doc/{sha}.html').expanduser()
    out_file.parent.mkdir(exist_ok=True)
    commit_url_pattern = f'https://gitlab.nxvms.dev/ft/ft/-/blob/{sha}/{{path}}#L{{lineno}}'
    with out_file.open('w', encoding='utf8') as f:
        formatter = _HTMLFormatter(f, commit_url_pattern)
        with formatter.in_doc():
            walk = _Walk(_root, formatter, [
                _root / 'arms',
                _root / 'tests',
                ])
            for d in _root.iterdir():
                walk.visit(d)
    artifact_store = make_artifact_store()
    print(artifact_store.store_one(out_file))
    out_latest = Path('~/.cache/nxft-doc/latest.html').expanduser()
    _logger.info("Copied to %s", out_latest)
    shutil.copyfile(out_file, out_latest)
    print(artifact_store.store_one(out_latest))
    if gitlab_ft_ft.get_full_sha('master') == sha:
        out_master = Path('~/.cache/nxft-doc/master.html').expanduser()
        _logger.info("Copied to %s", out_master)
        shutil.copyfile(out_file, out_master)
        print(artifact_store.store_one(out_master))
    return 0


class _Walk:

    def __init__(self, root, formatter: '_HTMLFormatter', exclude: Container[Path]):
        self._exclude = exclude
        self._formatter = formatter
        self._root = root

    def visit(self, f):
        if f.name.startswith('.'):
            _logger.debug("Skip starting with dot: %s", f)
        elif f.name == '__pycache__':
            _logger.debug("Skip __pycache__: %s", f)
        elif f.is_dir():
            if f in self._exclude:
                _logger.debug("Skip excluded: %s", f)
            else:
                init_py = f / '__init__.py'
                if init_py.exists():
                    self._visit_package(init_py)
        elif f.is_file():
            if f.suffix != '.py':
                _logger.debug("Skip unknown file suffix: %s", f)
            elif f.name == 'test.py' or f.name.startswith('test_'):
                _logger.debug("Skip test file: %s", f)
            elif f.name.startswith('_'):
                _logger.debug("Skip private file: %s", f)
            else:
                _logger.debug("Collect: %s", f)
                self._visit_module(f)
        else:
            _logger.debug("Skip unknown file type: %s", f)

    def _visit_module(self, path: Path):
        with self._formatter.in_file(path.name):
            contents = path.read_text(encoding='utf8')
            tree = ast.parse(contents)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    self._visit_class(node)
                elif isinstance(node, ast.FunctionDef):
                    self._visit_function(node)
                else:
                    pass

    def _visit_class(self, node):
        docstring = ast.get_docstring(node)
        if docstring is not None and _name_is_worth_showing(node.name):
            with self._formatter.in_class(_unparse_declaration(node), docstring):
                for member in ast.iter_child_nodes(node):
                    if isinstance(member, ast.FunctionDef):
                        self._visit_function(member)

    def _visit_package(self, init_py: Path):
        tree = ast.parse(init_py.read_text())
        docstring = ast.get_docstring(tree)
        all_names = []
        imports = {}
        for entry in tree.body:
            if isinstance(entry, ast.Assign) and len(entry.targets) == 1:
                [target] = entry.targets
                if isinstance(target, ast.Name) and target.id == '__all__':
                    if isinstance(entry.value, (ast.List, ast.Tuple, ast.Set)):
                        for v in entry.value.elts:
                            if isinstance(v, ast.Constant):
                                all_names.append(v.value)
            if isinstance(entry, ast.ImportFrom):
                if not entry.module.startswith('.'):
                    for alias in entry.names:
                        imports[alias.name] = entry.module
        with self._formatter.in_dir(init_py.parent.name, docstring):
            for name in all_names:
                if _name_is_worth_showing(name) and name in imports:
                    self._consider_output_imported(imports[name], name)
            for ff in init_py.parent.iterdir():
                if init_py.parent.name.startswith('_'):
                    _logger.debug("Skip private: %s", init_py.parent)
                else:
                    self.visit(ff)

    def _consider_output_imported(self, module_name, name):
        module = self._kind_of_import(module_name)
        for entry in module.body:
            if isinstance(entry, ast.ClassDef):
                if entry.name == name:
                    self._visit_class(entry)
            elif isinstance(entry, ast.FunctionDef):
                if entry.name == name:
                    self._visit_function(entry)
            else:
                pass

    def _consider_output_name(self, entry):
        docstring = ast.get_docstring(entry)
        if docstring:
            self._formatter.output_func(_unparse_declaration(entry), 0, docstring)

    def _visit_function(self, node):
        docstring = ast.get_docstring(node)
        headline = _unparse_declaration(node)
        if docstring is not None and _name_is_worth_showing(node.name):
            self._formatter.output_func(headline, node.lineno, docstring)

    @lru_cache()
    def _kind_of_import(self, imported: str):
        assert not imported.startswith('.')
        d, _, f = imported.rpartition('.')
        path = self._root.joinpath(*d.split('.'), f + '.py')
        return ast.parse(path.read_text())


def _unparse_declaration(node):
    n = deepcopy(node)
    n.body = []
    n.decorator_list = []
    return ast.unparse(n)


def _name_is_worth_showing(name):
    return not name.startswith(('_', 'test_'))


def _walk(pattern: str, *, exclude):
    _logger.info("Search %r for %r excluding %r", _root, pattern, exclude)

    def _w(f):
        if f.name.startswith('.'):
            _logger.debug("Skip starting with dot: %s", f)
        elif f.name == '__pycache__':
            _logger.debug("Skip __pycache__: %s", f)
        elif f.is_dir():
            if f in exclude:
                _logger.debug("Skip excluded: %s", f)
            else:
                _logger.debug("Recurse: %s", f)
                for ff in f.iterdir():
                    yield from _w(ff)
        elif f.is_file():
            if fnmatch.fnmatch(f.name, pattern):
                _logger.debug("Collect: %s", f)
                yield f
            else:
                _logger.debug("Skip unknown file suffix: %s", f)
        else:
            _logger.debug("Skip unknown file type: %s", f)

    yield from _w(_root)


class _HTMLFormatter:

    def __init__(self, output: TextIO, url_format):
        self._path = ''
        self._sha: str = url_format
        self._buffer = output
        self._nesting_level = 0
        self._xml = XMLGenerator(self._buffer)
        self._empty_levels = 0

    @contextmanager
    def in_doc(self):
        self._xml.startDocument()
        with self._tag('html', {}):
            self._xml.startElement('head', {})
            self._xml.endElement('head')
            self._xml.startElement('style', {})
            # language=CSS
            self._xml.ignorableWhitespace(textwrap.dedent(r'''
                body {
                    margin: 0;
                }
                #grid {
                    font-family: sans-serif;
                    display: grid;
                    grid-template-columns: 15em 45em;
                    max-width: 61em;
                    margin: 0 auto;
                }
                #toc {
                }
                #content {
                }
                aside {
                    position: fixed;
                    top: 0;
                    bottom: 0;
                    overflow-y: auto;
                }
                dl {
                    margin: unset;
                }
                dt {
                    font-weight: bold;
                }
                dd {
                }
                aside {
                    padding: 1em;
                }
                main {
                    padding: 0 1em 1em 1em;  /* dt has padding-top */
                }
                main > dl > dt {
                    padding-top: 1em;
                }
                dt.dir, dt.file {
                    font-size: 110%;
                }
                dt.dir::before {
                    content: "\1F4C2";
                }
                dt.file::before {
                    content: "\1F4C3";
                }
                p {
                    margin: unset;
                    word-break: break-word;  /* Long links and URLs */
                }
                '''))
            self._xml.endElement('style')
            with self._tag('body', {}):
                with self._tag('div', {'id': 'grid'}):
                    with self._tag('div', {'id': 'toc'}):
                        with self._tag('aside', {}):
                            pass
                    with self._tag('div', {'id': 'content'}):
                        with self._tag('main', {}):
                            with self._tag('dl', {}):
                                yield
                    with self._tag('script', {}):
                        # language=JS
                        self._xml.ignorableWhitespace(textwrap.dedent(r'''
                            let aside = document.querySelector('aside');
                            for (let header of document.querySelectorAll('main > dl > dt')) {
                                let element = document.createElement('a');
                                element.href = '#' + encodeURIComponent(header.id);
                                element.textContent = header.textContent;
                                aside.appendChild(element);
                                aside.appendChild(document.createElement('br'));
                            }
                            '''))

    def output_func(self, name, lineno, docstring):
        with self._tag('dt', {}):
            with self._tag('span', {}):
                self._xml.characters(name)
            self._xml.characters(' ')
            url = self._sha.format(path=self._path, lineno=lineno)
            self._xml.startElement('a', {'href': url})
            self._xml.characters('Git')
            self._xml.endElement('a')
        with self._tag('dd', {}):
            if docstring:
                paragraphs = docstring.split('\n\n')
                for paragraph in paragraphs:
                    with self._tag('p', {}):
                        self._xml.characters(paragraph)

    @contextmanager
    def _in(self, name, docstring: Optional[str], css_class: Optional[str] = None):
        if css_class is not None:
            class_attr = {'class': css_class}
        else:
            class_attr = {}
        attrs = {'id': name}
        with self._tag('dt', {**attrs, **class_attr}):
            self._xml.characters(name)
        with self._tag('dd', class_attr):
            if docstring:
                paragraphs = docstring.split('\n\n')
                for paragraph in paragraphs:
                    with self._tag('p', {}):
                        self._xml.characters(paragraph)
            with self._tag('dl', {}):
                self._nesting_level += 1
                yield
                self._nesting_level -= 1

    @contextmanager
    def in_dir(self, name: str, docstring):
        with self._in(name + '/', docstring, 'dir'):
            old_path = self._path
            self._path += name + '/'
            yield
            self._path = old_path

    @contextmanager
    def in_file(self, name: str):
        with self._in(name, None, 'file'):
            old_path = self._path
            self._path += name
            yield
            self._path = old_path

    @contextmanager
    def in_class(self, name, docstring):
        with self._in(name, docstring):
            yield

    @contextmanager
    def _tag(self, tag: str, attrs: Mapping[str, str]):
        self._xml.startElement(tag, attrs)
        yield
        self._xml.endElement(tag)


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())
