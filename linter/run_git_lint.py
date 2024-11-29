# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import re
import shlex
import string
import subprocess
import sys
from typing import Sequence


def _main(args: Sequence[str]):
    """Examine commits not merged into master (on upstream) up to a limit.

    It is expected that merge requests will have less commits than the limit.

    Work with bytes, not str to continue even with decoding errors.

    Log problems in merged commits too to demonstrate what would have been
    a problem and facilitate debugging.

    See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/2724986970/Python+script+rules
    """
    if os.getenv('DRY_RUN'):
        _logger.info("Script is running in dry run mode, stop execution")
        return 0
    if not args:
        revision = 'HEAD'
    else:
        [revision] = args
    problem_count = 0
    for sha, message in _get_unmerged_commits(revision, 'master', 100):
        for lineno, line in enumerate(message.splitlines()):
            for error in _validate_commit_message_line(sha, lineno, line):
                _output_problem(sha, line, error)
                problem_count += 1
    return 10 if problem_count > 0 else 0


def _validate_commit_message_line(revision, lineno, line):
    """Find problems in commit message line.

    This function should contain what would be written in a document.
    It should be dense and look declarative.
    Move parsing, string manipulation and the like to other functions.
    """
    yield from _ascii(line)
    yield from _printable_characters(line)
    if lineno == 1:
        yield from _must_be_empty(line)
    if lineno != 0 and (trailer := _GitTrailer.try_parse(line)):
        yield from _normalized_whitespace(line)
        yield from _allowed_trailers(trailer, [
            b'Affects', b'Change-Id', b'Fixes-Commit', b'Fixes-Review', b'See',
            ])
        if trailer.key() == b'Affects':
            yield from _points_to_file(revision, trailer)
    elif lineno != 0 and line.startswith(b'    '):
        # This is a line of code.
        pass
    else:
        yield from _normalized_whitespace(line)
        if lineno == 0:
            if line.startswith(b'Revert '):
                # Revert commit messages are auto-generated.
                pass
            else:
                yield from _allowed_tags(line, re.compile(rb'[A-Z]+-\d+'), [
                    b'Mediaserver API', b'Linter', b'Reporting', b'FT View',
                    b'ARMs', b'GUI', b'Distrib', b'Provisioning', b'Snapshots',
                    b'RCT', b'VirtualBox', b'Archive backup', b'GitLab Runner',
                    b'Task Master', b'OS Access', b'Installation', b'CA',
                    b'Licensing', b'LDAP', b'Updates',
                    ])
                yield from _must_not_end_with_period(line)
        yield from _max_length(80, line)
        yield from _correct_letter_case(line, [
            b'API', b'ARM', b'ARMs', b'CPU', b'ChromeDriver', b'FT', b'Git',
            b'GitLab', b'HTTP', b'HTTPS', b'JSON', b'KVM', b'Linux', b'OS',
            b'POSIX', b'PyCharm', b'Python', b'URL', b'VBox', b'VM',
            b'VirtualBox', b'WinRM', b'Windows', b'libvirt', b'pytest',
            b'RAM', b'VBoxManage'])


def _ascii(line):
    try:
        line.decode('ascii')
    except UnicodeDecodeError as e:
        yield str(e)


def _printable_characters(line):
    r"""Only printable characters.

    >>> assert 'printable' in [*_printable_characters(b'zero\0zero')][0]
    >>> assert 'printable' in [*_printable_characters(b'esc\x7fesc')][0]
    """
    for i, c in enumerate(line):
        if chr(c) not in string.printable:
            yield f"Non-printable character with code {c} at position {i}"


def _must_be_empty(line):
    if line:
        yield "Line after heading must be empty"


def _normalized_whitespace(line):
    r"""Nothing but spaces. No leading nor trailing spaces. One space at time.

    >>> assert 'feed' in [*_normalized_whitespace(b'form\ffeed')][0]
    >>> assert 'tab' in [*_normalized_whitespace(b'vertical\vtab')][0]
    >>> assert 'tab' in [*_normalized_whitespace(b'horizontal\ttab')][0]
    >>> assert 'consecutive' in [*_normalized_whitespace(b'two  spaces')][0]
    >>> assert not [*_normalized_whitespace(b'A good message')]
    """
    if line != line.lstrip():
        yield "Leading spaces"
    if line != line.rstrip():
        yield "Trailing spaces"
    if any(c in b'\t\n\r\v\f' for c in line):
        yield "No whitespace is allowed except the space; no tabs, no feeds"
    if b'  ' in line.strip():
        yield "Two consecutive spaces are not allowed"


def _max_length(length_limit, line):
    if len(line.strip()) > length_limit:
        yield f"Too long {len(line.strip())} > {length_limit}"


def _correct_letter_case(line: bytes, correct_case):
    """Force normal letter case. Counteract all-lower style.

    >>> [*_correct_letter_case(b"git's good", [b"Git"])]
    ["Word b'git' should be written as b'Git'"]
    >>> [*_correct_letter_case(b"in .git dir", [b"Git"])]
    []
    >>> [*_correct_letter_case(b"run 'git fetch'", [b"Git"])]
    []
    >>> [*_correct_letter_case(b"path/to/git/repo", [b"Git"])]
    []
    >>> [*_correct_letter_case(b'Write "Git", not "git" or "GIT"', [b"Git"])]
    []
    """
    line = re.sub(rb"(?<=\w)(?:'s|'ve|n't)", b" ", line)
    line = re.sub(rb"'.*?'", b" ", line)
    line = re.sub(rb'".*?"', b" ", line)
    line = re.sub(rb"\(\),;:\.(?=\s|$)", b" ", line)
    words = re.split(rb"\s+", line)
    lower_case = {
        correct.lower(): correct
        for correct in correct_case
        }
    for word in words:
        if word.lower() not in lower_case:
            continue
        correct = lower_case[word.lower()]
        if word == correct:
            continue
        yield f"Word {word} should be written as {correct}"


def _must_not_end_with_period(line):
    if line.rstrip().endswith(b'.'):
        yield "Must not end with period"


def _allowed_tags(line, ticket_re, allowed_tags):
    [head, has_colon, _tail] = line.partition(b':')
    if has_colon:
        tags = head.split(b', ')
        for tag in tags:
            if not ticket_re.fullmatch(tag) and tag not in allowed_tags:
                yield f"Tag {tag} not allowed, allowed are: tickets and {allowed_tags}"


def _allowed_trailers(trailer, allowed_trailers):
    if trailer.key() not in allowed_trailers:
        yield f"Trailer {trailer.key()} is not among {allowed_trailers}"


def _points_to_file(revision, trailer: '_GitTrailer'):
    trailer_path = trailer.value().decode()
    try:
        _git(['cat-file', '-e', f'{revision}:{trailer_path}'])
    except subprocess.CalledProcessError as e:
        if e.returncode == 128:
            yield f"Trailer {trailer.key()} does not point to an existing file"
        else:
            raise


class _GitTrailer:
    """Parse Git trailer.

    See: https://git-scm.com/docs/git-interpret-trailers

    >>> trailer = _GitTrailer(b'Fixes-Commit: 3f9e84ac37217e63dda6b6f06f48809f31beb441')
    >>> trailer.key()
    b'Fixes-Commit'
    >>> trailer.value()
    b'3f9e84ac37217e63dda6b6f06f48809f31beb441'
    >>> _GitTrailer.try_parse(b'Normal text in natural language.') is None
    True
    """

    def __init__(self, line):
        self._line = line
        self._match = re.fullmatch(rb'(?P<key>[-\w]+):\s*(?P<value>.+)', line)
        if self._match is None:
            raise NotAGitTrailerError(f"Not a Git trailer: {line}")

    def __repr__(self):
        return f'{self.__class__.__name__}({self._line!r})'

    @classmethod
    def try_parse(cls, line):
        try:
            return cls(line)
        except NotAGitTrailerError:
            return None

    def key(self):
        return self._match['key']

    def value(self):
        return self._match['value']


class NotAGitTrailerError(Exception):
    pass


def _get_unmerged_commits(ref, remote_branch, depth):
    return _log_commit_hashes_and_messages([ref, f'^{ref}~{depth}', f'^{remote_branch}'])


def _log_commit_hashes_and_messages(refs):
    output = _git(['log', '-z', *refs, '--format=format:%H:%B'])
    lines = output.split(b'\0') if output else []
    r = []
    for line in lines:
        commit, message = line.split(b':', 1)
        r.append((commit.decode(), message))
    _logger.info("Commits: %d", len(r))
    return r


def _git(commit):
    command = ['git', *commit]
    if os.name == 'nt':
        _logger.info("Run: %s", subprocess.list2cmdline(command))
    else:
        _logger.info("Run: %s", shlex.join(command))
    return subprocess.check_output(command)  # may be affected by GIT_DIR env variable


def _output_problem(sha, line, error):
    sys.stdout.write(sha + ' ')
    sys.stdout.buffer.write(line)
    sys.stdout.write(' ' + error + os.linesep)
    sys.stdout.flush()


_logger = logging.getLogger()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(_main(sys.argv[1:]))
