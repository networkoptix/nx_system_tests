@rem Disables updates.
@rem See: https://docs.microsoft.com/de-de/security-updates/windowsupdateservices/18127499.
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoUpdate /t REG_DWORD /d 1 /f
net stop wuauserv
sc config wuauserv start= disabled

@rem Another way to stop updates -- make all connection metered.
@rem Takes effect on the start of DusmSvc -- Data Usage service.
for /f %%k in ('reg query HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces') do (
    reg add "HKLM\SOFTWARE\Microsoft\DusmSvc\Profiles\%%~nk\*" /v UserCost /t REG_DWORD /d 2 /f
)

@rem The third way to stop updates - set a pause for the Windows Update
@rem Windows Update allows you to pause updates for up to 28 days. However, in the Windows Registry,
@rem the pause duration can be set to any desired period.
@rem See: https://stackoverflow.com/questions/62424065/pause-windows-update-for-up-to-35-days-and-find-out-until-which-date-updates-are/64862952#64862952
REG ADD HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\UX\Settings /v PauseUpdatesExpiryTime /t REG_SZ /d "2033-01-30T18:00:00" /f
REG ADD HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\UX\Settings /v PauseFeatureUpdatesStartTime /t REG_SZ /d "2023-12-01T01:00:00" /f
REG ADD HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\UX\Settings /v PauseFeatureUpdatesEndTime /t REG_SZ /d "2033-01-30T18:00:00" /f
REG ADD HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\UX\Settings /v PauseQualityUpdatesStartTime /t REG_SZ /d "2023-12-01T01:00:00" /f
REG ADD HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\UX\Settings /v PauseQualityUpdatesEndTime /t REG_SZ /d "2033-01-30T18:00:00" /f

@rem Setup WinRM.
@rem Firewall rule is enabled as a part of `quickconfig`.
PowerShell -NonInteractive -ExecutionPolicy Unrestricted -File %~dp0\MakeNetworksPrivate.ps1
call winrm quickconfig -quiet
call winrm set winrm/config @{MaxEnvelopeSizekb="65536"}
call winrm set winrm/config/Service @{AllowUnencrypted="true"}
call winrm set winrm/config/Service/Auth @{Basic="true"}
call winrm set winrm/config/Client @{AllowUnencrypted="true"}
call winrm set winrm/config/Client @{TrustedHosts="*"}
call winrm set winrm/config/Client/Auth @{Basic="true"}
sc config WinRM start= auto

@rem First, guest client authentication must be allowed to access software share.
reg add "HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters" /v AllowInsecureGuestAuth /t REG_DWORD /d 1 /f

@rem When used with network shares (UNC paths), `pushd` creates network drive, which is unmounted on `popd`.
@rem `start "" /wait` is a way to wait for window application.
@rem Installers, whichever type they are of, usually can be installed without interaction. See help (`/?` parameter).
pushd "\\vboxsvr\.prerequisites"
start "" /wait "NM34_x64.exe" /Q
mkdir "C:\Sysinternals"
tar -xf "SysinternalsSuite.zip" -C"C:\Sysinternals"
popd

@rem Install Windows SDK
start "" /wait "E:\winsdksetup.exe" /features OptionId.WindowsDesktopDebuggers OptionId.WindowsPerformanceToolkit /q

@rem Allow SMB and pings.
netsh advfirewall firewall set rule group="File and Printer Sharing" new enable=yes
netsh advfirewall firewall set rule group="Network Discovery" new enable=yes

@rem Allow Terminal Services and RDP.
netsh advfirewall firewall set rule group="Remote Desktop" new enable=yes
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f

@rem Disable UAC.
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v ConsentPromptBehaviorAdmin /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v ConsentPromptBehaviorUser /t REG_DWORD /d 0 /f

@rem Enable ACPI button. By default, a VM cannot be powered off by "pressing" the PowerOff button
reg add HKLM\SOFTWARE\Policies\Microsoft\Power\PowerSettings\7648EFA3-DD9C-4E3E-B566-50F929386280 /v ACSettingIndex /t REG_DWORD /d 3
reg add HKLM\SOFTWARE\Policies\Microsoft\Power\PowerSettings\7648EFA3-DD9C-4E3E-B566-50F929386280 /v DCSettingIndex /t REG_DWORD /d 3

@rem Set power plan to High Performance and disable hibernation and all timeouts.
PowerCfg /SetActive SCHEME_MIN
PowerCfg /Hibernate OFF
PowerCfg /Change monitor-timeout-ac 0
PowerCfg /Change monitor-timeout-dc 0
PowerCfg /Change disk-timeout-ac 0
PowerCfg /Change disk-timeout-dc 0
PowerCfg /Change standby-timeout-ac 0
PowerCfg /Change standby-timeout-dc 0
PowerCfg /Change hibernate-timeout-ac 0
PowerCfg /Change hibernate-timeout-dc 0

@rem Disable page file to reduce VM image size.
WMIC ComputerSystem set AutomaticManagedPageFile=False
WMIC PageFileSet Delete

@rem Disable NTFS timestamp updates
@rem See: https://dfir.ru/2018/12/08/the-last-access-updates-are-almost-back/
REG ADD HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v NTFSDisableLastAccessUpdate /t REG_DWORD /d 0x80000001 /f

@rem The services NcdAutoSetup ('Network Connected Devices Auto-Setup') and netprofm ('Network List Service')
@rem can restart the network stack, which may cause problems known as 'WinRM timeout'.
@rem NcdAutoSetup can be disabled in base image, netprofm should be disabled only during tests
@rem as many other services depend on it.
sc config NcdAutoSetup start= disabled

@rem Clear and enable system and application logs
cmd /C %~dp0\ClearAndEnableWindowsLogs.cmd

@rem ------------------- THE LAST COMMAND SHUTS DOWN THE MACHINE --------------------
TaskKill /F /IM Sysprep.exe
%SystemRoot%\System32\Sysprep\sysprep.exe /audit /shutdown
@rem --------------------------- NOTHING BELOW THIS LINE ----------------------------
