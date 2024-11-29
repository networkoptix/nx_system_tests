@rem ------------------- THE LAST COMMAND SHUTS DOWN THE MACHINE --------------------
TaskKill /F /IM Sysprep.exe
%SystemRoot%\System32\Sysprep\sysprep.exe /oobe /shutdown /unattend:%~dp0\Unattend.xml
@rem --------------------------- NOTHING BELOW THIS LINE ----------------------------
