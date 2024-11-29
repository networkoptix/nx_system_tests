$ad_admin_pwd = ConvertTo-SecureString "WellKnownPassword1!@#" -AsPlainText -Force
Set-ADAccountPassword -Identity Administrator -NewPassword $ad_admin_pwd
Set-ADUser -Identity Administrator -PasswordNeverExpires 1
