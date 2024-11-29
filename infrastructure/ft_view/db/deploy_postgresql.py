# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import secrets
import string
from pathlib import Path

from provisioning import CompositeCommand
from provisioning import Fleet
from provisioning import InstallCommon
from provisioning import InstallSecret
from provisioning import Run


def main():
    host = 'sc-ft003.nxlocal'
    path = Path(f'~/.config/.secrets/postgres-{host}/.pgpass').expanduser()
    try:
        [first_line, *_] = path.read_text().splitlines()
        [_, full_access_password] = first_line.rsplit(':', maxsplit=1)
    except FileNotFoundError:
        alphabet = string.ascii_letters + string.digits
        full_access_password = ''.join(secrets.choice(alphabet) for i in range(16))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((
            f'127.0.0.1:5432:ft_view:ft_view:{full_access_password}\n'
            f'127.0.0.1:5432:ft_view:ft_view_read_only:WellKnownPassword2\n'))
    quoted_password = "'" + full_access_password.replace("'", "''") + "'"
    migration_files = [
        Path(__file__).parent / 'schema.sql',
        ]
    Fleet([host]).run([
        # If .pgpass already exists on remote - consider database deployed.
        Run('! sudo -u ft test -s ~ft/.pgpass'),
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get -y install postgresql-14'),
        InstallCommon('postgres', 'infrastructure/ft_view/db/pg_hba.conf', '/etc/postgresql/14/main/'),
        InstallCommon('postgres', 'infrastructure/ft_view/db/postgresql.conf', '/etc/postgresql/14/main/'),
        Run('sudo systemctl restart postgresql.service'),
        InstallCommon('root', 'infrastructure/ft_view/db/ft_view_db.sql', '/tmp/sql_files/'),
        Run('sudo -u postgres psql -f /tmp/sql_files/ft_view_db.sql'),
        Run(f'sudo -u postgres psql -c "ALTER USER ft_view WITH PASSWORD {quoted_password}"'),
        CompositeCommand([
            InstallCommon('root', str(path), '/tmp/sql_files/')
            for path in migration_files
            ]),
        CompositeCommand([
            Run(f'sudo PGPASSWORD={quoted_password} -u postgres psql -f /tmp/sql_files/{path.name} -d ft_view -U ft_view')
            for path in migration_files
            ]),
        Run('rm -rf /tmp/sql_files'),
        InstallSecret('ft', str(path), '~ft/'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
