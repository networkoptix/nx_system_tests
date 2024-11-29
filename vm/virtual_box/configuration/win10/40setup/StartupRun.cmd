rem ----- System Settings, Software and Scheduling OOBE -----
@rem Windows Update allows you to pause updates for up to 28 days. However, in the Windows Registry,
@rem the pause duration can be set to any desired period.
@rem See: https://stackoverflow.com/questions/62424065/pause-windows-update-for-up-to-35-days-and-find-out-until-which-date-updates-are/64862952#64862952
REG ADD HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU /v NoAutoUpdate /t REG_DWORD /d 1 /f
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
@rem The Desktop Client uses OpenGL to build its user interface. However, as virtual machines lack 3D accelerators,
@rem standard OpenGL drivers don't function, preventing the Desktop Client from working inside virtual machines.
@rem The MESA 3D Graphics Library provides a software implementation of the OpenGL API called LLVMPipe.
@rem See: https://docs.mesa3d.org/drivers/llvmpipe.html
copy /Y opengl32sw.dll C:\Windows\System32\
@rem VLC allows to record the screen
start "" /wait msiexec /quiet /i vlc-3.0.19-win64.msi
popd

@rem Install Windows SDK
start "" /wait "E:\winsdksetup.exe" /features OptionId.WindowsDesktopDebuggers OptionId.WindowsPerformanceToolkit /q

@rem Allow SMB and pings.
netsh advfirewall firewall set rule group="File and Printer Sharing" new enable=yes
netsh advfirewall firewall set rule group="Network Discovery" new enable=yes

netsh advfirewall firewall add rule name="VLC" dir=in action=allow program="C:\Program Files\VideoLAN\VLC\vlc.exe" enable=yes

@rem Enable Microsoft iSCSI Initiator service
sc config "msiscsi" start=auto

@rem Allow Terminal Services and RDP.
@rem See: https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/unattend/microsoft-windows-terminalservices-localsessionmanager-fdenytsconnections
netsh advfirewall firewall set rule group="Remote Desktop" new enable=yes
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f

@rem Turn off multicast name resolution. By default, MDNS service listen port 5353.
@rem Mediaserver binds to it at the same time without any notification hence breaking the
@rem camera's DNS-SD discovery feature, when using unicast addresses. Using unicast for DNS-SD
@rem is a workaround for cases when multicast address cannot be used because of networking
@rem schemes, that cannot forward non-unicast traffic (e.g. VBox intnet).
@rem (Yes, this is a workaround for another workaround to work.)
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient" /v EnableMulticast /t REG_DWORD /d 0 /f

@rem Disable UAC.
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v ConsentPromptBehaviorAdmin /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v ConsentPromptBehaviorUser /t REG_DWORD /d 0 /f

@rem Turn off Windows Defender notifications.
reg add "HKLM\Software\Policies\Microsoft\Windows Defender Security Center\Notifications" /v DisableNotifications /t REG_DWORD /d 1 /f

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

@rem Disable Windows Search service
sc config "wsearch" start=disabled

@rem Disable NTFS timestamp updates
@rem See: https://dfir.ru/2018/12/08/the-last-access-updates-are-almost-back/
REG ADD HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v NTFSDisableLastAccessUpdate /t REG_DWORD /d 0x80000001 /f

@rem Disable page file to reduce VM image size.
WMIC ComputerSystem set AutomaticManagedPageFile=False
WMIC PageFileSet Delete

@rem The services NcdAutoSetup ('Network Connected Devices Auto-Setup') and netprofm ('Network List Service')
@rem can restart the network stack, which may cause problems known as 'WinRM timeout'.
@rem NcdAutoSetup can be disabled in base image, netprofm should be disabled only during tests
@rem as many other services depend on it.
sc config NcdAutoSetup start= disabled

@rem Clear and enable system and application logs
cmd /C %~dp0\ClearAndEnableWindowsLogs.cmd

@rem ------------------- THE LAST COMMAND SHUTS DOWN THE MACHINE --------------------
TaskKill /F /IM Sysprep.exe
%SystemRoot%\System32\Sysprep\sysprep.exe /oobe /shutdown /unattend:%~dp0\Unattend.xml
@rem The command above schedules OOBE mode, which activates Windows.
@rem To save snapshot in the non-activated state,
@rem schedule Audit mode with /audit as in scripts in other stages.
@rem --------------------------- NOTHING BELOW THIS LINE ----------------------------
