@rem After starting the VM, the .NET Runtime Optimization Service precompiles .Net assemblies and consumes a lot of CPU time.
@rem See: https://learn.microsoft.com/en-us/archive/blogs/davidnotario/what-is-mscorsvw-exe-and-why-is-it-eating-up-my-cpu-what-is-this-new-clr-optimization-service
@rem Find and disable all NGEN scheduled tasks.
schtasks /query /fo csv /nh | findstr /C:".NET Framework NGEN" > c:\ngen_tasks
FOR /F "tokens=1 delims=," %%N in ('type c:\ngen_tasks') DO (
  schtasks /Change /Disable /Tn %%N
)
@rem Run the service manually.
cd "C:\Windows\Microsoft.NET"
FOR /F %%N in ('dir /s /b ngen.exe') DO (
  %%N executeQueuedItems
)
