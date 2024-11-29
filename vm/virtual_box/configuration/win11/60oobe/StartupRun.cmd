rem ----- Activation and Compression after OOBE -----

@rem This script will run only after all OOBE process has been finished.

@rem By unknown reason, the Windows activation does not run automatically as it should. So, activate it explicitly.
@rem slmgr.vbs is called via cscript because of a pop-up window after a successful activation
cscript //B "%windir%\system32\slmgr.vbs" /ato

@rem Make virtual disk size less: compact, defragment, consolidate free space on disk, zero-fill free space.
Compact /CompactOS:Always
defrag C: /X /H /U /V
"C:\Sysinternals\sdelete.exe" /accepteula -z C:

shutdown /s /t 0
