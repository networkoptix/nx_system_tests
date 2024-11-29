# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import AddUser
from provisioning._config_files import CommentLine
from provisioning._core import Run
from provisioning._known_hosts import FirstConnect
from provisioning._pubkey import AddPubKey
from provisioning._pubkey import RepoPubKey
from provisioning._users import AddUserToGroup
from provisioning.fleet import beg_ft002

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    beg_ft002.run([
        FirstConnect(),
        ])
    # CUT: Personal accounts configuration
    beg_ft002.run([
        # Quick SSH login
        CommentLine('/etc/pam.d/sshd', 'pam_motd.so'),
        CommentLine('/etc/pam.d/sshd', 'pam_mail.so'),
        CommentLine('/etc/pam.d/login', 'pam_motd.so'),
        CommentLine('/etc/pam.d/login', 'pam_mail.so'),
        ])
