# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
from datetime import datetime
from typing import Sequence
from xml.etree import cElementTree as et

from os_access._windows_access import WindowsAccess


def start_in_graphic_mode(windows_access: WindowsAccess, command_args: Sequence[str], task_name=None):
    """Start in interactive (graphic) mode using the Task Scheduler hack.

    This is the only known hack to run something in interactive session
    when in non-interactive session.
    The interactive session must exist, of course.
    WinRM connection is non-interactive, hence the need for it.
    See: https://serverfault.com/q/568055/208965
    """
    shell = windows_access.winrm_shell()
    command_line = shell.args_to_command_line(command_args)
    if task_name is None:
        task_name = "Run " + command_line
    # To see the prohibited characters,
    # type any of them in the name field in the task window.
    task_name = re.sub('[\\\\/:*?"<>|]+', '-', task_name)
    task_name = re.sub('-+', '-', task_name)
    if len(task_name) > 237:
        raise ValueError(
            f"Task name cannot be more than 237 character(s), "
            f"consider passing task name explicitly: "
            f"currently {len(task_name)} character(s): {task_name!r}")
    if len(command_line) > 261:
        cmd_file = windows_access.path('c:\\', task_name + '.cmd')
        _logger.info(
            "Task Scheduler command cannot be more than 261 character(s), "
            "execute via %s: currently %d character(s): %r",
            cmd_file, len(command_line), command_line)
        cmd_file.write_text(f'start {task_name!r} {command_line}')
        command = str(cmd_file)
        arguments = ''
    else:
        command = shell.args_to_command_line(command_args[0:1])
        arguments = shell.args_to_command_line(command_args[1:])
    root = _create_xml(
        task_name,
        windows_access.username,
        command,
        str(windows_access.home()),
        arguments,
        )
    xml_file = windows_access.home().joinpath('FT_schtasks_config.xml')
    xml_file.write_text(et.tostring(root, encoding='unicode'))
    shell.run([
        'schtasks', '/create', '/xml', xml_file, '/tn', task_name, '/f'])
    shell.run([
        'schtasks', '/run', '/tn', task_name,
        ])
    shell.run([
        'schtasks', '/delete', '/tn', task_name, '/f',
        ])


def _create_xml(task_name, author, command: str, working_dir: str, command_arguments: str = ''):
    now = datetime.now()
    # Round the seconds to the nearest minute
    formatted_now = now.strftime("%Y-%m-%dT%H:%M:%S")
    task_uri = r'http://schemas.microsoft.com/windows/2004/02/mit/task'
    unreal_condition = r"<QueryList><Query><Select Path='Application'>*[@x=1 and @x=2]</Select></Query></QueryList>"
    et.register_namespace("", task_uri)
    # Create the root element
    root = et.Element("{%s}Task" % task_uri)
    root.set("version", "1.2")

    # Create the RegistrationInfo element
    registration_info = et.SubElement(root, "RegistrationInfo")
    et.SubElement(registration_info, "Date").text = formatted_now
    et.SubElement(registration_info, "Author").text = author
    et.SubElement(registration_info, "URI").text = task_name

    # Create the Settings element
    settings = et.SubElement(root, "Settings")
    et.SubElement(settings, "DisallowStartIfOnBatteries").text = "false"
    et.SubElement(settings, "StopIfGoingOnBatteries").text = "false"
    et.SubElement(settings, "MultipleInstancesPolicy").text = "IgnoreNew"
    idle_settings = et.SubElement(settings, "IdleSettings")
    et.SubElement(idle_settings, "Duration").text = "PT10M"
    et.SubElement(idle_settings, "WaitTimeout").text = "PT1H"
    et.SubElement(idle_settings, "StopOnIdleEnd").text = "true"
    et.SubElement(idle_settings, "RestartOnIdle").text = "false"

    # create the Triggers element
    triggers = et.SubElement(root, "Triggers")
    event_trigger = et.SubElement(triggers, "EventTrigger")
    et.SubElement(event_trigger, "StartBoundary").text = formatted_now
    et.SubElement(event_trigger, "Subscription").text = unreal_condition

    # create the Actions element
    actions = et.SubElement(root, "Actions")
    exec_elem = et.SubElement(actions, "Exec")
    et.SubElement(exec_elem, "Command").text = command
    et.SubElement(exec_elem, "WorkingDirectory").text = working_dir
    if command_arguments:
        et.SubElement(exec_elem, "Arguments").text = command_arguments

    return root


_logger = logging.getLogger(__name__)
