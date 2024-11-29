# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import os
import subprocess
import sys
import venv
from argparse import ArgumentParser
from pathlib import Path


def run_in_venv(cmd):
    """Shortcut that creates venv and runs Python from it.

    For more elaborate usages, opt for making venv ang running separately.
    """
    venv_python = make_venv()
    p = subprocess.run([venv_python, *cmd])
    return p.returncode


def make_venv(project_dir: os.PathLike = '.'):
    """Create venv. Re-use if nothing changed.

    Rely only on the hash file. Do not validate anything else.
    It is too laborious to validate a venv properly,
    but the chances that anything would break are low.
    """
    requirements_txt = _repo_root / project_dir / 'requirements.txt'
    venv_dir = _repo_root / project_dir / '.venv'
    venv_python = venv_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if venv_python.absolute() == Path(sys.executable):
        raise AlreadyInTheSameVenv()
    hash_file = venv_dir / '.hash'
    our_hash = hashlib.md5()
    our_hash.update(sys.version.encode())
    our_hash.update(Path(__file__).read_bytes())
    our_hash.update(b'\0')  # Hash also the "border" between files.
    our_hash.update(requirements_txt.read_bytes())
    our_hash = our_hash.hexdigest()
    if not hash_file.exists() or hash_file.read_text() != our_hash:
        hash_file.unlink(missing_ok=True)  # In case this run fails.
        venv.create(venv_dir, clear=True, with_pip=True)
        # Save settings in pip.conf (Unix) or pip.ini (Windows) in the venv.
        # Old versions may be removed from PyPI. Use Python package store.
        # Reduce risks of accidentally unpinned requirement versions.
        pip = [venv_python, '-m', 'pip', '-q']
        subprocess.run([*pip, 'config', '--site', 'set', 'install.find_links', 'https://python-packages.us.nxft.dev/'], check=True)
        subprocess.run([*pip, 'config', '--site', 'set', 'install.no_index', 'yes'], check=True)
        subprocess.run([*pip, 'config', '--site', 'set', 'global.disable_pip_version_check', 'yes'], check=True)
        subprocess.run([*pip, 'config', '--site', 'set', 'global.no_color', 'yes'], check=True)
        subprocess.run([*pip, 'install', '-r', requirements_txt], check=True)
        hash_file.write_text(our_hash)
    return venv_python


class AlreadyInTheSameVenv(Exception):
    pass


_repo_root = Path(__file__).parent
assert str(_repo_root) in sys.path


def main(args):
    parser = ArgumentParser(description=(
        "run Python from venv if any arguments follow; "
        "otherwise, only create or re-use a venv; "
        "another options are to create a venv from the calling code "
        "(but it's less convenient as a single command line) and "
        "to create a venv from the target script itself "
        "(but in this case, imports from the venv wouldn't work); "
        "the downside of this option is yet another long-running process"))
    parser.add_argument('--project-dir', '-p', default='.', help=(
        "base dir for .venv and requirements.txt;\n"
        f"relative to {_repo_root};\n"
        "default: %(default)r"))
    parser.usage = parser.format_usage().rstrip() + ' [ARGS ...]\n'
    args, command = parser.parse_known_args(args)
    venv_python = make_venv(args.project_dir)
    if command:
        p = subprocess.run([venv_python, *command])
        return p.returncode
    else:
        print(venv_python)
        return 0


if __name__ == '__main__':
    exit(main(sys.argv[1:]))
