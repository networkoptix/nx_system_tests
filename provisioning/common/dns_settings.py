# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import InstallCommon
from provisioning._core import Fleet
from provisioning._core import Run
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft002_cloud
from provisioning.fleet import sc_ft003_master


def main():
    fl = Fleet.compose([
        sc_ft003_master,
        sc_ft002_cloud,
        sc_ft,
        ])
    fl.run([
        # Disable DNS "proxy" server on localhost.
        # systemd-resolved is suspected of responding with
        # "No address associated with hostname" or
        # "Temporary failure in name resolution".
        # This is an attempt to resolve the issue.
        # See: https://networkoptix.atlassian.net/browse/FT-2182
        Run('sudo mkdir -p /etc/systemd/resolved.conf.d/'),
        InstallCommon('root', 'provisioning/common/disable_resolved.conf', '/etc/systemd/resolved.conf.d/'),
        Run('sudo systemctl restart systemd-resolved.service'),

        # Zabbix seems to cache DNS settings.
        # Hosts are shown as red (unavailable) if not restarted.
        Run('sudo systemctl restart zabbix-agent.service'),
        ])
    fl.run([
        # Work around DNS server failures. "Cache" the most popular DNS names
        # to avoid test errors because of the DNS server failures.
        # Cleanup old results before querying domains
        Run(r'sudo sed "/\; ft-dns-settings/d" -i.bak /etc/hosts'),
        # Caveat: dig does not output original domain (e.g. sc-ft001 will be transformed to sc-ft001.nxlocal)
        # which makes dig output difficult to parse when executed with multiple domains at once.
        # All hostnames marked with comment "; ft-dns-settings" for easier cleanup
        Run('for i in sc-ft{001..024}; do dig +short -4 $i.nxft.dev | xargs -I {} echo "{} $i $i.nxlocal $i.nxft.dev ; ft-dns-settings" | sudo tee -a /etc/hosts; done'),
        Run('for i in beg-ft{001..002}; do dig +short -4 $i.nxft.dev | xargs -I {} echo "{} $i $i.nxlocal $i.nxft.dev ; ft-dns-settings" | sudo tee -a /etc/hosts; done'),
        Run('dig +short -4 artifactory.us.nxteam.dev | xargs -I {} echo "{} artifactory.us.nxteam.dev ; ft-dns-settings" | sudo tee -a /etc/hosts'),
        # Check /etc/hosts with "getent ahosts" and "getent ahosts sc-ft0xx" commands.
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
