@rem Make virtual disk size less: compact, defragment, consolidate free space on disk, zero-fill free space.
Compact /CompactOS:Always
defrag C: /X /H /U /V
"C:\Sysinternals\sdelete.exe" /accepteula -z C:

shutdown /s /t 0
