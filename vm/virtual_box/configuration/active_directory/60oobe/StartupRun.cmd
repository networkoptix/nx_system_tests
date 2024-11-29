@rem This script will run only after all OOBE process has been finished.

@rem Visual explorer adjustments.
REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v Hidden /t REG_DWORD /d 1 /f
REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v HideFileExt /t REG_DWORD /d 0 /f
REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v ShowSuperHidden /t REG_DWORD /d 1 /f
REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v Start_ShowRun /t REG_DWORD /d 1 /f
REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v StartMenuAdminTools /t REG_DWORD /d 1 /f
REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v TaskbarGlomLevel /t REG_DWORD /d 2 /f
REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v TaskbarSmallIcons /t REG_DWORD /d 1 /f

shutdown /s /t 0
