@rem Install certificate to avoid confirmation GUI window.
@rem Last argument (called modifier) `Certs` is poorly documented.
@rem If `Certs` modifier is not provided, certificate chain gets into wrong group in `CertMgr`.
@rem When run first time, CertUtil fails with "File not found" error, `-f` cures it.
CertUtil -addStore -f TrustedPublisher D:\NetKVM\w10\amd64\netkvm.cat Certs

PnPUtil /add-driver d:\NetKVM\w10\amd64\netkvm.inf /install

@rem ------------------- THE LAST COMMAND SHUTS DOWN THE MACHINE --------------------
TaskKill /F /IM Sysprep.exe
%SystemRoot%\System32\Sysprep\sysprep.exe /audit /shutdown
@rem --------------------------- NOTHING BELOW THIS LINE ----------------------------
