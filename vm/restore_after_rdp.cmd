rem Create a batch file on the remote host, put this command in the batch file.
rem On Windows 10, session id is 1. On a legacy Windows, session id is 0.
rem tscon.exe needs to be run elevated (as Administrator).
rem Create an elevated shortcut for the batch file.
rem Place the shortcut on desktop of the host.
rem When you want to disconnect the session and unlock the remote host
rem restoring the local user's desktop, double click / tap the shortcut.
rem See: https://www.tenforums.com/network-sharing/16159-disable-login-screen-after-remote-desktop-session.html
rem See: https://www.tenforums.com/network-sharing/16159-disable-login-screen-after-remote-desktop-session-post340105.html#post340105
rem See: https://docs.microsoft.com/en-us/windows-server/administration/windows-commands/tscon
tscon.exe 1 /dest:console
