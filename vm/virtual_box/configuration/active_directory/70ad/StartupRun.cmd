@rem Prepare ADDS.
PowerShell -NonInteractive -ExecutionPolicy Unrestricted -File %~dp0\ConfigureADDS.ps1

shutdown /s /t 0
