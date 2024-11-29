# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import ctypes
import os
import subprocess
import sys
from contextlib import ExitStack
from ctypes import POINTER
from ctypes import Structure
from ctypes.wintypes import BOOL
from ctypes.wintypes import BYTE
from ctypes.wintypes import DWORD
from ctypes.wintypes import HANDLE
from ctypes.wintypes import LPCWSTR
from ctypes.wintypes import LPDWORD
from ctypes.wintypes import LPVOID
from ctypes.wintypes import LPWSTR
from ctypes.wintypes import ULONG
from ctypes.wintypes import WORD
from typing import Sequence
from typing import Tuple

from vm.virtual_box.run_as_user._process_result import ProcessResult


def run_as_local_user(user: str, args: Sequence[str]) -> ProcessResult:
    # see https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createprocesswithlogonw
    # See https://learn.microsoft.com/en-us/windows/win32/procthread/creating-a-child-process-with-redirected-input-and-output?redirectedfrom=MSDN
    stdout_read_handle, stdout_write_handle = _create_pipe()
    stderr_read_handle, stderr_write_handle = _create_pipe()
    startup_info = _Startupinfo()
    startup_info.cb = ctypes.sizeof(startup_info)
    startup_info.hStdOutput = stdout_write_handle
    startup_info.hStdError = stderr_write_handle
    startup_info.dwFlags = 0x100  # Set STARTF_USESTDHANDLES
    process_info = _ProcessInformation()
    executable = args[0]
    command = subprocess.list2cmdline(args)
    try:
        CreateProcessWithLogonW(
            user,
            os.environ['USERDOMAIN'],
            os.getenv('PREFERRED_USER_PASSWORD', 'WellKnownPassword2'),
            # The logon option must be zero.
            # LOGON_WITH_PROFILE (0x1) does not work for VirtualBox, as subsequent
            # VBoxManage.exe command calls fail with ERROR_KEY_DELETED/0x800703fa (0x800703fa).
            # Possibly it has something to do with the way Windows loads user profile and with
            # VBoxSVC process.
            # LOGON_NETCREDENTIALS_ONLY (0x2) uses user only for remote calls, local commands
            # are running without user switch.
            0x0,
            executable,
            command,
            0x08000000,  # Set CREATE_NO_WINDOW flag
            None,
            None,
            ctypes.byref(startup_info),
            ctypes.byref(process_info),
            )
    except OSError as e:
        if e.winerror == 1326:
            # Username should be correct, there is a problem with password.
            raise RuntimeError(
                f"{e} Check that user {user!r} exists and password is set to the default "
                "FT password or provided via 'PREFERRED_USER_PASSWORD' env variable")
        raise
    # Close write handles of pipe before reading from it;
    # otherwise ReadFile will get stuck.
    CloseHandle(stdout_write_handle)
    CloseHandle(stderr_write_handle)
    timeout_sec = 60
    # Read from pipes occurs after process is finished. It is done to simplify logic.
    # Entire command output should fit in pipe buffer.
    # Otherwise, ReadFile must be done periodically in overlapped mode with waiting on
    # pipe handles and process handle via WaitForMultipleObjects.
    wait_result = WaitForSingleObject(process_info.hProcess, timeout_sec * 1000)
    process_exit_code = DWORD()
    GetExitCodeProcess(process_info.hProcess, ctypes.byref(process_exit_code))
    CloseHandle(process_info.hProcess)
    CloseHandle(process_info.hThread)
    with ExitStack() as exit_stack:
        exit_stack.callback(CloseHandle, stdout_read_handle)
        exit_stack.callback(CloseHandle, stderr_read_handle)
        if wait_result == _WaitResult.WAIT_OBJECT_0:
            stdout = _read_from_handle(stdout_read_handle)
            stderr = _read_from_handle(stderr_read_handle)
        elif wait_result == _WaitResult.WAIT_TIMEOUT:
            raise TimeoutError(f"Command {command} did not finish in {timeout_sec:.1f} seconds")
        elif wait_result == _WaitResult.WAIT_ABANDONED:
            raise RuntimeError("WaitForSingleObject returned _WaitResult.WAIT_ABANDONED")
        elif wait_result == _WaitResult.WAIT_FAILED:
            raise ctypes.WinError(ctypes.get_last_error())
        else:
            raise RuntimeError(f"Unexpected WaitForSingleObject result: {wait_result}")
        return ProcessResult(process_exit_code.value, stdout, stderr, command)


def _create_pipe() -> Tuple[HANDLE, HANDLE]:
    # See https://learn.microsoft.com/en-us/windows/win32/procthread/creating-a-child-process-with-redirected-input-and-output?redirectedfrom=MSDN
    security_attributes = _SecurityAttributes()
    security_attributes.nLength = ctypes.sizeof(security_attributes)
    security_attributes.lpSecurityDescriptor = None
    security_attributes.bInheritHandle = True
    read_handle = HANDLE()
    write_handle = HANDLE()
    CreatePipe(
        ctypes.byref(read_handle),
        ctypes.byref(write_handle),
        ctypes.byref(security_attributes),
        50 * 1024 * 1024,
        )
    # Ensure the read handle to the pipe used for output is not inherited.
    # HANDLE_INHERIT_FLAG (mask 0x1) is set to zero.
    SetHandleInformation(read_handle, 0x1, 0)
    return read_handle, write_handle


def _read_from_handle(handle) -> bytes:
    size = 1024 * 1024
    buffer = ctypes.c_buffer(size)
    result = bytearray()
    read_bytes = DWORD()
    while True:
        # BrokenPipeError should be treated as EOF
        # See https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-readfile
        try:
            ReadFile(handle, buffer, size, ctypes.byref(read_bytes), None)
        except BrokenPipeError:
            break
        if read_bytes.value == 0:
            break
        result.extend(buffer.raw[:read_bytes.value])
    return result


def _raise_on_error(result, func, args):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return args


class _Startupinfo(Structure):
    _fields_ = [
        ('cb', DWORD),
        ('lpReserved', LPWSTR),
        ('lpDesktop', LPWSTR),
        ('lpTitle', LPWSTR),
        ('dwX', DWORD),
        ('dwY', DWORD),
        ('dwXSize', DWORD),
        ('dwYSize', DWORD),
        ('dwXCountChars', DWORD),
        ('dwYCountChars', DWORD),
        ('dwFillAttribute', DWORD),
        ('dwFlags', DWORD),
        ('wShowWindow', WORD),
        ('cbReserved2', WORD),
        ('lpReserved2', POINTER(BYTE)),
        ('hStdInput', HANDLE),
        ('hStdOutput', HANDLE),
        ('hStdError', HANDLE),
        ]


class _ProcessInformation(Structure):
    _fields_ = [
        ('hProcess', HANDLE),
        ('hThread', HANDLE),
        ('dwProcessId', DWORD),
        ('dwThreadId', DWORD),
        ]


class _SecurityAttributes(Structure):
    _fields_ = [
        ('nLength', DWORD),
        ('lpSecurityDescriptor', LPVOID),
        ('dwProcessId', BOOL),
        ]


class _Overlapped(Structure):
    _fields_ = [
        ('Internal', POINTER(ULONG)),
        ('InternalHigh', POINTER(ULONG)),
        ('hEvent', HANDLE),
        ('Pointer', LPVOID),
        ]


advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
CreateProcessWithLogonW = advapi32.CreateProcessWithLogonW
CreateProcessWithLogonW.argtypes = [
    LPCWSTR,  # lpUsername
    LPCWSTR,  # lpDomain
    LPCWSTR,  # lpPassword
    DWORD,  # dwLogonFlags
    LPCWSTR,  # lpApplicationName
    LPWSTR,  # lpCommandLine
    DWORD,  # dwCreationFlags
    LPWSTR,  # lpEnvironment
    LPCWSTR,  # lpCurrentDirectory
    POINTER(_Startupinfo),  # lpStartupInfo
    POINTER(_ProcessInformation),  # lpProcessInformation
    ]
CreateProcessWithLogonW.errcheck = _raise_on_error
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
CreatePipe = kernel32.CreatePipe
CreatePipe.argtypes = [
    POINTER(HANDLE),  # hReadPipe
    POINTER(HANDLE),  # hWritePipe
    POINTER(_SecurityAttributes),  # lpPipeAttributes
    DWORD,  # nSize
    ]
CreatePipe.errcheck = _raise_on_error
SetHandleInformation = kernel32.SetHandleInformation
SetHandleInformation.argtypes = [
    HANDLE,  # hObject
    DWORD,  # dwMask
    DWORD,  # dwFlags
    ]
SetHandleInformation.errcheck = _raise_on_error
CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [HANDLE]
CloseHandle.errcheck = _raise_on_error
WaitForSingleObject = kernel32.WaitForSingleObject
WaitForSingleObject.argtypes = [HANDLE, DWORD]
ReadFile = kernel32.ReadFile
ReadFile.argtypes = [
    HANDLE,  # hFile,
    LPVOID,  # lpBuffer,
    DWORD,  # nNumberOfBytesToRead,
    LPDWORD,  # lpNumberOfBytesRead,
    POINTER(_Overlapped),  # lpOverlapped
    ]
ReadFile.errcheck = _raise_on_error
GetExitCodeProcess = kernel32.GetExitCodeProcess
GetExitCodeProcess.argtypes = [
    HANDLE,  # hProcess
    POINTER(DWORD),  # lpExitCode
    ]
GetExitCodeProcess.errcheck = _raise_on_error


class _WaitResult:
    # See https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject
    WAIT_FAILED = 0xFFFFFFFF
    WAIT_ABANDONED = 0x80
    WAIT_OBJECT_0 = 0x0
    WAIT_TIMEOUT = 0x102


if __name__ == '__main__':
    # To open VirtualBox Manager within your main user, run:
    # > runas /user:%USERDOMAIN%\ft-199 /savecred "C:\Program Files\Oracle\VirtualBox\VirtualBox.exe"
    # or RDP to virtual machine (29900 is default port for ft-199 user):
    # > mstsc /v:127.0.0.1:29900
    result = run_as_local_user('ft-199', [r'C:\Windows\System32\cmd.exe', '/c', *sys.argv[1:]])
    print(result.stdout.decode())
    print(result.stderr.decode())
