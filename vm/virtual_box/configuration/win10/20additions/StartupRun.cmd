rem ----- VirtualBox Guest Additions -----

@rem When run first time, CertUtil fails with "File not found" error, `-f` cures it.
CertUtil -addStore -f TrustedPublisher E:\cert\vbox-sha1.cer
CertUtil -addStore -f TrustedPublisher E:\cert\vbox-sha256.cer
E:\VBoxWindowsAdditions.exe /force /S /I

@rem ------------------- THE LAST COMMAND SHUTS DOWN THE MACHINE --------------------
TaskKill /F /IM Sysprep.exe
%SystemRoot%\System32\Sysprep\sysprep.exe /audit /shutdown
@rem --------------------------- NOTHING BELOW THIS LINE ----------------------------
