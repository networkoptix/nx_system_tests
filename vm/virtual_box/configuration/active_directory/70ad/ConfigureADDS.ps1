Install-WindowsFeature -Name AD-Domain-Services -IncludeManagementTools
Import-Module ADDSDeployment
$safe_mode_admin_pwd = ConvertTo-SecureString "WellKnownPassword2!@#" -AsPlainText -Force
Install-ADDSForest -DomainName "local.nx" -CreateDnsDelegation:$false `
    -DatabasePath "C:\Windows\NTDS" -DomainMode "WinThreshold" `
    -DomainNetbiosName "local" -ForestMode "WinThreshold" `
    -InstallDns:$true -LogPath "C:\Windows\NTDS" `
    -NoRebootOnCompletion:$true -SysvolPath "C:\Windows\SYSVOL" `
    -Force:$true -SafeModeAdministratorPassword $safe_mode_admin_pwd
