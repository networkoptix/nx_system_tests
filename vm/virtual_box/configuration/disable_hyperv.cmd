echo Make sure script is running with admin rights.

@rem Disable any "Hyper-V"-related features
@rem that may prevent VirtualBox from using VT-x/AMD-V.
dism.exe /online /norestart /disable-feature:Microsoft-Hyper-V-All
dism.exe /online /norestart /disable-feature:Microsoft-Hyper-V
dism.exe /online /norestart /disable-feature:Microsoft-Hyper-V-Tools-All
dism.exe /online /norestart /disable-feature:Microsoft-Hyper-V-Management-PowerShell
dism.exe /online /norestart /disable-feature:Microsoft-Hyper-V-Hypervisor
dism.exe /online /norestart /disable-feature:Microsoft-Hyper-V-Services
dism.exe /online /norestart /disable-feature:Microsoft-Hyper-V-Management-Clients
dism.exe /online /norestart /disable-feature:VirtualMachinePlatform
bcdedit /set hypervisorlaunchtype off

@rem Disable Memory Integrity protection
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled /t REG_DWORD /d 0 /f

@rem If none of those steps helped, try going through
@rem the list in the first post: https://forums.virtualbox.org/viewtopic.php?f=25&t=99390
@rem And don't forget to add useful steps to this script :)

@rem Also, check VT-x/AMD-V enabled in your BIOS/UEFI settings.

echo Please restart your PC for the changes to take effect.
