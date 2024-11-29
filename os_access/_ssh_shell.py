# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import errno
import logging
import math
import socket
import time
from abc import ABCMeta
from abc import abstractmethod
from selectors import DefaultSelector
from selectors import EVENT_READ
from typing import Optional

import paramiko
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.serialization import load_ssh_private_key

from os_access._command import Run
from os_access._posix_shell import PosixShell
from os_access._posix_shell import augment_script
from os_access._posix_shell import command_to_script
from os_access._posix_shell import quote_arg

_logger = logging.getLogger(__name__)


class SshNotConnected(Exception):

    def __init__(self, ssh, message):
        super().__init__(message)
        self.ssh = ssh


class _SshRun(Run, metaclass=ABCMeta):

    def __init__(self, channel: paramiko.Channel, args):
        super(_SshRun, self).__init__(args)
        self._channel = channel
        self._peer_addr = self._channel.getpeername()
        self._selector = DefaultSelector()
        self._selector.register(self._channel, EVENT_READ)

    def __repr__(self):
        addr, port = self._peer_addr[:2]  # for ipv6 we get (host, port, flowinfo, scopeid)
        return f"<{self.__class__.__name__} at {addr}:{port}>"

    @property
    def returncode(self):
        if not self._channel.exit_status_ready():
            return None
        return self._channel.exit_status

    def receive(self, timeout_sec):
        self._channel.setblocking(False)
        # TODO: Wait for exit status too.
        self._selector.select(timeout_sec)
        chunks = []
        for recv in [self._channel.recv, self._channel.recv_stderr]:
            try:
                chunk = recv(16 * 1024)
            except TimeoutError:  # Non-blocking: times out immediately if no data.
                chunks.append(b'')
                continue
            if len(chunk) == 0:
                chunks.append(None)
                continue
            chunks.append(chunk)
        return chunks

    def wait(self, timeout=None):
        if timeout is not None:
            self.communicate(timeout_sec=timeout)
        return self._channel.recv_exit_status()

    def close(self):
        self._selector.close()
        self._channel.close()


class _PseudoTerminalSshRun(_SshRun):

    def __init__(self, channel, script):
        super(_PseudoTerminalSshRun, self).__init__(channel, script)
        self._channel.get_pty()
        self._channel.invoke_shell()
        if '\n' in script:
            _logger.info("Run in PTY on %s:\n%s", self, script)
        else:
            _logger.info("Run in PTY on %s: %s", self, script)
        script += '\n' 'exit $?'
        self._channel.sendall(script)
        self._channel.send('\n')
        self._open_streams = {
            "STDOUT": (self._channel.recv, _logger.getChild('stdout')),
            "STDERR": (self._channel.recv_stderr, _logger.getChild('stderr')),
            }

    def send(self, input, is_last=False):
        raise NotImplementedError(
            "Sending data to pseudo-terminal is prohibited intentionally; "
            "it's equivalent to pressing keys on keyboard, "
            "therefore, there is no straightforward way to pass binary data; "
            "on other hand, interaction with terminal is not needed by now")

    def _send_ctrl(self, char):
        """Emulate pressing Ctrl+<char>.

        See ASCII table with control characters to get idea how character codes are formed.
        """
        code = chr(ord(char.upper()) - ord(b'@'))
        _logger.debug('Send Ctrl+%s', char.decode())
        bytes_sent = self._channel.send(code)
        assert bytes_sent == 1

    def terminate(self):
        """Send Ctrl+C, Ctrl+C, repeat Ctrl+D until channel is closed.

        Ctrl+C is sent twice, because sometimes apps handle first time they encounter this signal.
        Then Ctrl+D is sent to close the terminal. Due to possible race condition inside
        the paramiko module, we can't rely on the fact that the ssh channel will not be closed
        at the moment of sending shortcuts. The simplest solution possible is return after
        a first exception. Moreover, we still ought to send the EOF (Ctrl+D) if the program was
        terminated via the SIGINT signal (Ctrl+C).
        This method cannot guarantee robust closure as SIGKILL is not sent. Other options are:
        - Ctrl+Z, `kill %% -9`, Ctrl+D -- just a bit complicated;
        - Ctrl+Backslash, Ctrl+D -- will do a core dump if `ulimit -c` allows.
        """
        # Mimic the Subprocess behavior ignoring the close call if a process is already finished
        if self._channel.exit_status > -1:
            return
        try:
            self._send_ctrl(b'C')
            time.sleep(0.5)  # Allow for quick cleanup.
            self._send_ctrl(b'C')
            timeout_sec = 30
            sleep_time_sec = 0.1
            for _ in range(math.ceil(timeout_sec / sleep_time_sec)):
                time.sleep(sleep_time_sec)
                self._send_ctrl(b'D')
            raise RuntimeError(f"Timed out ({timeout_sec} seconds) waiting for {self} to terminate")
        except socket.error as exception:
            if exception.errno is None:
                return
            raise

    kill = terminate


class _StraightforwardSshRun(_SshRun):
    """Run command over SSH without pseudo-terminal allocation.

    SSH protocol of most common versions (as opposed to newest ones) is not capable of send signals
    or terminate process. To control process with signals, run command with pseudo-terminal.
    """

    def __init__(self, channel, script):
        super(_StraightforwardSshRun, self).__init__(channel, script)
        if '\n' in script:
            _logger.info("Run on %s:\n%s", self, script)
        else:
            _logger.info("Run on %s: %s", self, script)
        self._channel.exec_command(script)
        self._open_streams = {
            "STDOUT": (self._channel.recv, _logger.getChild('stdout')),
            "STDERR": (self._channel.recv_stderr, _logger.getChild('stderr')),
            }

    def send(self, input, is_last=False):
        self._channel.settimeout(10)  # Must never time out assuming process always open stdin and read from it.
        input = memoryview(input)
        if input:
            bytes_sent = self._channel.send(input[:16 * 1024])
            _logger.debug("Chunk of input sent: %d bytes.", bytes_sent)
            if bytes_sent == 0:
                _logger.warning("Write direction preliminary closed from the other side.")
                # TODO: Raise exception.
        else:
            bytes_sent = 0
        if is_last and not input[bytes_sent:]:
            _logger.debug("Shutdown write direction.")
            self._channel.shutdown_write()
        return bytes_sent

    def terminate(self):
        raise NotImplementedError(f"Can't terminate a non-interactive {self.args}")

    def kill(self):
        raise NotImplementedError(f"Can't kill a non-interactive {self.args}")


class BaseSsh(PosixShell, metaclass=ABCMeta):

    def __init__(
            self,
            hostname: str,
            port: int,
            username: str,
            key: Optional[str],
            banner_timeout: Optional[float] = None):
        self._hostname = hostname
        self._port = port
        self._username = username
        self._banner_timeout = banner_timeout
        if key is not None:
            key = key.encode('ascii')
            if key.startswith(b'-----BEGIN OPENSSH PRIVATE KEY-----'):
                key = load_ssh_private_key(key, None)
            else:
                key = load_pem_private_key(key, None)
            self._key = paramiko.RSAKey(key=key)
        else:
            self._key = None

    def __repr__(self):
        return '<{!s}>'.format(command_to_script([
            'ssh', '{!s}@{!s}'.format(self._username, self._hostname),
            '-p', self._port,
            ]))

    def netloc(self):
        return f'{self._hostname}:{self._port}'

    def Popen(self, args, cwd=None, env=None, terminal=False):
        if isinstance(args, str):  # Interpret a string as a shell script.
            augmented_script = augment_script(args, cwd=cwd, set_eux=True, env=env)
        else:  # Interpret a list of strings as an executable name with args.
            args = command_to_script(args)
            if env is not None:
                env_args = [name + '=' + quote_arg(value) for name, value in env.items()]
                args = ' '.join(env_args) + ' ' + args
            augmented_script = augment_script(args, cwd=cwd, set_eux=False, env=None)
        channel = self._client().get_transport().open_session()
        # Run object is further responsible for channel closure.
        if terminal:
            return _PseudoTerminalSshRun(channel, augmented_script)
        else:
            return _StraightforwardSshRun(channel, augmented_script)

    def _client(self):
        try:
            return self._ssh_client
        except AttributeError:
            pass
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())  # Ignore completely.
        sock = self._get_proxy_command_socket()
        try:
            ssh_client.connect(
                str(self._hostname), port=self._port,
                username=self._username,
                pkey=self._key,
                look_for_keys=not self._key,
                allow_agent=not self._key,
                sock=sock,
                banner_timeout=self._banner_timeout,
                disabled_algorithms={"macs": [
                    # Tackle incorrect message authentication code (MAC) error.
                    # It appeared on a single host PC with an Ubuntu 18.04 VM.
                    # The connection is interrupted, and a corresponding log
                    # message appears in /var/log/auth on the server.
                    # It was reproduced when connecting from the another PC,
                    # as well as from the host; both Windows, Ubuntu not tried.
                    # Everything is fine with other hosts and VM OSes.
                    "hmac-sha2-256",  # May cause MAC mismatch.
                    "hmac-sha2-512",  # May cause MAC mismatch.
                    # "hmac-sha2-256-etm@openssh.com",
                    # "hmac-sha2-512-etm@openssh.com",
                    "hmac-sha1",  # Less secure.
                    "hmac-md5",  # Less secure.
                    "hmac-sha1-96",  # Less secure.
                    "hmac-md5-96",  # Less secure.
                    ]},
                )
        except paramiko.ssh_exception.NoValidConnectionsError as e:
            raise SshNotConnected(self, "Cannot connect to {}: {} (is port opened?)".format(self, e))
        except paramiko.ssh_exception.SSHException as e:
            raise SshNotConnected(self, "Cannot connect to {}: {} (is service started? using VirtualBox?)".format(self, e))
        except socket.gaierror as e:
            if e.errno == -2:
                raise RuntimeError(
                    f"DNS server responded that {self._hostname!r} is not known to it")
            raise
        self._ssh_client = ssh_client
        return self._ssh_client

    def _sftp(self):
        try:
            return self._sftp_client
        except AttributeError:
            pass
        self._sftp_client = self._client().open_sftp()
        return self._sftp_client

    def close(self):
        try:
            sftp = self._sftp_client
        except AttributeError:
            pass
        else:
            sftp.close()
            del self._sftp_client
        try:
            ssh = self._ssh_client
        except AttributeError:
            pass
        else:
            ssh.close()
            del self._ssh_client

    @abstractmethod
    def is_working(self) -> bool:
        pass

    @abstractmethod
    def _get_proxy_command_socket(self) -> Optional[paramiko.ProxyCommand]:
        pass


class Ssh(BaseSsh):

    def is_working(self):
        """Try opening connection and see if something can be received.

        This method is usually used to check if remote OS is reachable.
        Paramiko floods to logs on ERROR level if it can't connect.

        The only actual thing, specific to SSH is that both parties send
        something to each other. The code may be factored out of here and used
        for other purposes with little modification.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            try:
                sock.connect((socket.gethostbyname(self._hostname), self._port))
            except TimeoutError as e:
                _logger.info(
                    "Checked SSH on %s:%d: %r",
                    self._hostname, self._port, e)
                return False
            except ConnectionRefusedError as e:
                _logger.info(
                    "Checked SSH on %s:%d: %r; is port opened?",
                    self._hostname, self._port, e)
                return False
            except OSError as e:
                if e.errno == errno.EHOSTUNREACH:
                    return False
                raise
            try:
                # In SSH both parties must send something upon connection --
                # no need to send anything to the other side.
                # The other party can send any data before an identification --
                # complicated to check.
                data = sock.recv(1)
            except TimeoutError as e:
                _logger.info(
                    "Checked SSH on %s:%d: %r; has VM booted up?",
                    self._hostname, self._port, e)
                return False
            if not data:
                _logger.info(
                    "Checked SSH on %s:%d: connection closed unexpectedly; "
                    "is port opened within VM?",
                    self._hostname, self._port)
                return False
            try:
                self.run(['whoami'])
            except paramiko.ssh_exception.SSHException:
                return False
        return True

    def _get_proxy_command_socket(self):
        return None
