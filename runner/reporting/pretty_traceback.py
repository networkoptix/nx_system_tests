# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import html
import inspect
import logging
import traceback
from abc import abstractmethod
from collections.abc import Sequence
from contextlib import AbstractContextManager
from contextlib import contextmanager
from pathlib import Path
from string import Template
from typing import Any
from typing import NamedTuple


def dump_traceback(exception, run_dir):
    tb = TracebackDump(exception)
    tb.save(TracebackToText(run_dir / 'python_traceback.log'))
    tb.save(TracebackToHTML(run_dir / 'python_traceback.html'))


class TracebackDump:

    def __init__(self, exc: Exception):
        self._info = []
        while True:
            frames = []
            for [python_frame, error_line] in traceback.walk_tb(exc.__traceback__):
                try:
                    [src_code, start_line_src] = inspect.getsourcelines(python_frame)
                except OSError:
                    # Source code may not be available for precompiled modules (*.pyc) or,
                    # for example, for modules built with tools such as PyInstaller.
                    src_code = None
                    start_line_src = None
                    _logger.warning(
                        'Failed to get source code for %s', python_frame.f_code.co_filename)
                frame = _Frame(
                    filename=Path(python_frame.f_code.co_filename),
                    src_code=src_code,
                    error_line=error_line,
                    start_line_src=start_line_src,
                    local_variables=python_frame.f_locals,
                    )
                frames.append(frame)
            exception_info = _ExceptionInfo(exc, frames)
            self._info.append(exception_info)
            if exc.__context__ is None:
                break
            exc = exc.__context__

    def save(self, formatter: '_Formatter'):
        with formatter.write_content():
            for exception_info in self._info:
                formatter.write_exception(exception_info.exception)
                for frame in exception_info.frames:
                    formatter.write_frame(frame)


class _Formatter:

    @abstractmethod
    def write_exception(self, exc: BaseException):
        pass

    @abstractmethod
    def write_frame(self, frame: '_Frame'):
        pass

    @abstractmethod
    def write_content(self) -> AbstractContextManager[None]:
        pass


class TracebackToText(_Formatter):
    _separator = "=" * 72

    def __init__(self, file: Path):
        self._file = file
        self._content = []

    def write_exception(self, exc: BaseException):
        self._content.append(f"Exception: {exc!r}".rstrip())
        self._content.append(self._separator)

    def write_frame(self, frame: '_Frame'):
        self._content.append(str(frame.filename))
        if frame.src_code is not None:
            error_line = frame.error_line - frame.start_line_src
            code = frame.src_code[:error_line]
            if len(frame.src_code) > error_line and len(frame.src_code[error_line]) > 1:
                error_code_line = f'>{frame.src_code[error_line][1:]}'
            else:
                # The source code line could be empty or might not exist at all, at least in cases
                # where the source code has been changed after starting execution.
                error_code_line = '>'
            code.append(error_code_line)
        else:
            code = ['<no source code found>']
        self._content.append(''.join(code))
        self._content.append("Local variables:")
        for name, value in frame.local_variables.items():
            try:
                self._content.append(f'{name}={value!r}')
            except Exception:
                _logger.exception('Failed to format local variable %s', name)
        self._content.append(self._separator)

    @contextmanager
    def write_content(self):
        self._content.append(self._separator)
        yield
        self._file.write_text('\n'.join(self._content), encoding='utf-8')


class TracebackToHTML(_Formatter):

    def __init__(self, file: Path):
        self._file = file
        self._content = []

    def write_exception(self, exc: BaseException):
        template = Template("""
            <h3><pre style="color: red">$text_exception</pre></h3>
            <hr>
        """)
        text_exception = repr(exc).replace('\\n', '\n')
        self._content.append(template.substitute(text_exception=text_exception))

    def write_frame(self, frame: '_Frame'):
        frame_template = Template("""
            <span style="color: blue">$filename</span>
            <pre style="font-size: 110%">$src_code</pre>
            <b>Local variables:</b>
            <table>
                $local_variables
            </table>
            <hr>
        """)
        var_template = Template("""
            <tr>
                <td></td> <td>$name</td> <td>=</td> <td>$value</td>
            </tr>
        """)
        error_line_tmpl = Template("""<code style="color: red">$code_line</code>""")
        if frame.src_code is not None:
            error_line = frame.error_line - frame.start_line_src
            last_line = min(error_line + 2, len(frame.src_code))
            src_code = frame.src_code[:last_line]
            src_code = [f'{n:4} {line}' for n, line in enumerate(src_code, frame.start_line_src)]
            src_code = [html.escape(line) for line in src_code]
            try:
                src_code[error_line] = error_line_tmpl.substitute(
                    code_line=f'>>>>{src_code[error_line][4:]}')
            except IndexError:
                src_code = [html.escape('<source code has been changed>')]
        else:
            src_code = [html.escape('<no source code found>')]
        variables = []
        max_len_of_value = 1000
        for name, value in frame.local_variables.items():
            try:
                value_text = repr(value)
            except Exception:
                _logger.exception('Failed to format local variable %s', name)
            else:
                if len(value_text) > max_len_of_value:
                    value_text = f'{value_text[:max_len_of_value]} ...'
                variables.append(
                    var_template.substitute(name=name, value=html.escape(value_text)))
        one_frame_html = frame_template.substitute(
            filename=frame.filename,
            src_code=''.join(src_code),
            local_variables=''.join(variables),
            )
        self._content.append(one_frame_html)

    @contextmanager
    def write_content(self):
        self._content.append('<!DOCTYPE html>')
        self._content.append('<html>')
        self._content.append('<body style="background: lightgray">')
        yield
        self._content.append('</body>')
        self._content.append('</html>')
        self._file.write_text('\n'.join(self._content), encoding='utf-8')


class _Frame(NamedTuple):

    filename: Path
    src_code: list[str]
    start_line_src: int
    error_line: int
    local_variables: dict[str, Any]


class _ExceptionInfo(NamedTuple):

    exception: BaseException
    frames: Sequence[_Frame]


_logger = logging.getLogger(__name__)
