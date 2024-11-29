# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Documented datacenter machines configuration and tools for that.

The goal is to keep configuration in code under version control.
It serves as documentation for what is installed and configured.
Nothing may be changed on the machines without a provisioning script.

Provisioning is the process of creating and setting up IT infrastructure.
See: https://www.redhat.com/en/topics/automation/what-is-provisioning

Every script here is a set of commands run on a fleet.

Every action is formulated in terms of a command.
In most cases, it is a Run object
or an instance of a subclass of CompositeCommand.
It is desirable that commands be written in the most raw form,
so that it is clear what is being run and it is easy to copy.

Commands must be idempotent.
The second run must not "accumulate" changes.
Running it multiple times must be safe.

Commands should not be executed directly. Only via a fleet.
This allows for reordering, logging, interaction with the user
and forces simpler commands that do not use results of each other,
which makes it easier to run them manually.

Provisioning scripts are intended to be run manually by someone who has enough
permissions to do so. Scripts can be run from personal workstations, which can
run on Windows or Linux.

Provisioning scripts should be run one by one, without automation or scripting.
Provisioning is error-prone and sometimes dangerous. If a script fails,
the human who runs it must investigate the problem. If it succeeds, it's still
recommended to examine the script output and what the script actually did.

Do not call SSH functions from deployment scripts.

Do not call run methods of commands from deployment scripts.

Configuration must be as non-invasive as possible.
Alter the defaults as little as possible.
The default configuration is usually the most tested and secure.
"""
from provisioning._core import Command
from provisioning._core import CompositeCommand
from provisioning._core import Fleet
from provisioning._core import InstallCommon
from provisioning._core import InstallSecret
from provisioning._core import Run
from provisioning._pubkey import AddPubKey
from provisioning._pubkey import HomePubKey
from provisioning._pubkey import RepoPubKey
from provisioning._users import AddUser

__all__ = [
    'AddPubKey',
    'AddUser',
    'Command',
    'CompositeCommand',
    'Fleet',
    'HomePubKey',
    'InstallCommon',
    'InstallSecret',
    'RepoPubKey',
    'Run',
    'Run',
    ]
