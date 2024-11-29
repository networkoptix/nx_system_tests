@rem Without waiting the next command fails.
timeout /t 30

@rem Set domain admin password.
PowerShell -NonInteractive -ExecutionPolicy Unrestricted -File %~dp0\SetDomainAdminPassword.ps1

shutdown /s /t 0
