# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import shlex
from pathlib import Path

from provisioning import Fleet
from provisioning import InstallCommon
from provisioning import InstallSecret
from provisioning._core import Command
from provisioning._core import Run
from provisioning._ssh import ssh
from provisioning._ssh import ssh_input
from provisioning._ssh import ssh_still
from provisioning.fleet import beg_ft001
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft003_master


def main():
    sc_ft003_master.run([
        _InstallElasticsearch(),
        _InstallKibana(),
        ])
    Fleet.compose([beg_ft001, sc_ft]).run([
        InstallSecret('ft', 'provisioning/ft_services/elasticsearch.netrc', '~ft/.config/.secrets/'),
        ])


class _InstallElasticsearch(Command):

    def __init__(self):
        self._root_url = 'http://127.0.0.1:9201/'
        self._index_template_name = 'ft-logs-template'
        self._indexes_templates = ['ft-logs-*', 'ft-alerts-*']

    def __repr__(self):
        return f'{_InstallElasticsearch.__name__}()'

    def run(self, host):
        Run('wget -N --progress=dot:giga https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.8.2-amd64.deb').run(host)
        r = ssh(host, 'sudo apt-get install ~/elasticsearch-8.8.2-amd64.deb')
        output = r.stdout.decode()
        password = _get_password(host, output)
        InstallCommon('elasticsearch', 'provisioning/ft_services/elasticsearch.yml', '/etc/elasticsearch/').run(host)
        Run('sudo systemctl daemon-reload').run(host)
        Run('sudo systemctl enable elasticsearch.service').run(host)
        Run('sudo systemctl restart elasticsearch.service').run(host)
        self._create_template_index(host, password)
        self._create_role(host, password)
        r = ssh_still(host, 'sudo /usr/share/elasticsearch/bin/elasticsearch-users useradd ft-reporter -p WellKnownPassword2 -r ft-reporter')
        if r.returncode != 0:
            if b'ERROR: User [ft-reporter] already exists\n' in r.stderr:
                _logger.info("User already created")
            else:
                r.check_returncode()

    def _create_template_index(self, host: str, password: str):
        ssh_input(host, 'dd status=none of=.elastic.netrc', f'machine 127.0.0.1 login elastic password {password}\n'.encode())
        url = self._root_url + f'_index_template/{self._index_template_name}'
        path = Path(__file__).parent.parent.parent / 'infrastructure/elasticsearch_logging/template.json'
        ssh_input(host, 'dd status=none of=elastic-template.json', path.read_bytes())
        r = ssh_still(
            host,
            f'curl -sS --fail-with-body --netrc-file .elastic.netrc -X PUT -H "Content-Type: application/json" -d @elastic-template.json {shlex.quote(url)}',
            )
        if r.returncode != 0:
            reply = json.loads(r.stdout.decode())
            if reply['error']['type'] == 'resource_already_exists_exception':
                _logger.info("Index template already created")
            else:
                r.check_returncode()
        ssh(host, 'shred --remove .elastic.netrc')

    def _create_role(self, host: str, password: str):
        ssh_input(host, 'dd status=none of=.elastic.netrc', f'machine 127.0.0.1 login elastic password {password}\n'.encode())
        role = json.dumps({
            'indices': [
                {'names': self._indexes_templates, 'privileges': ['write', 'create_index']},
                ]})
        ssh_input(host, 'dd status=none of=elastic-role.json', role.encode('ascii'))
        url = self._root_url + '_security/role/ft-reporter'
        ssh(
            host,
            f'curl -sS --fail-with-body --netrc-file .elastic.netrc -H "Content-Type: application/json" -d @elastic-role.json {shlex.quote(url)}',
            )
        ssh(host, 'shred --remove .elastic.netrc')


def _get_password(host, output):
    password_from_output = _parse_password(output)
    path = Path(f'~/.config/.secrets/elastic@{host}.txt').expanduser()
    if password_from_output is not None:
        path.write_text(password_from_output)
        _logger.info("Password saved: %s", path)
        return password_from_output
    else:
        try:
            password_from_file = path.read_text()
        except FileNotFoundError:
            raise RuntimeError(f"Could not parse password nor find {path}")
        else:
            return password_from_file


def _parse_password(output):
    for line in output.splitlines():
        if line.startswith('The generated password'):
            password = line.split(':')[1].strip()
            return password
    return None


class _InstallKibana(Command):

    def __repr__(self):
        return f'{_InstallKibana.__name__}()'

    def run(self, host):
        Run('wget -N --progress=dot:giga https://artifacts.elastic.co/downloads/kibana/kibana-8.8.2-amd64.deb').run(host)
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install ./kibana-8.8.2-amd64.deb').run(host)
        r = ssh_still(host, 'sudo /usr/share/elasticsearch/bin/elasticsearch-users useradd ft-kibana -p WellKnownPassword2 -r kibana_system')
        if r.returncode != 0:
            if b'ERROR: User [ft-kibana] already exists\n' in r.stderr:
                _logger.info("User already created")
            else:
                r.check_returncode()
        InstallCommon('kibana', '_internal/kibana.yml', '/etc/kibana/').run(host)
        Run('sudo systemctl daemon-reload').run(host)
        Run('sudo systemctl enable kibana.service').run(host)
        Run('sudo systemctl restart kibana.service').run(host)
        InstallCommon('ft', 'provisioning/ft_services/kibana.us.nginx.conf', '/etc/nginx/sites-available/').run(host)
        Run('sudo ln -f -s /etc/nginx/sites-available/kibana.us.nginx.conf /etc/nginx/sites-enabled/kibana').run(host)
        Run('sudo systemctl reload nginx').run(host)


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
