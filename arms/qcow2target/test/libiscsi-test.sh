#!/bin/bash

set -e

BINARY_PATH=${1:?The first parameter must be qcow2target executable}
ADMIN_BINARY_NAME=${2:? The second parameter must be qcow2target admin executable name}

BINARY_DIR="$(dirname "${BINARY_PATH}")"
BINARY_NAME="$(basename "${BINARY_PATH}")"

UNIX_SOCKET_PATH="qcow2target.sock"
TARGET=iqn.2008-05.com.networkoptix.ft.arms:example.tgt
HOST_PORT=127.0.0.1:3260

# Kill previous iscsi tgt server instance
kill -9 "$(pidof "$BINARY_NAME")" || echo "No process present"

# Start iscsi tgt server
cd "${BINARY_DIR}"
 "./$BINARY_NAME" iscsi "${UNIX_SOCKET_PATH}" 2> tgt.log &
# wait for API to get online
sleep 1

"./${ADMIN_BINARY_NAME}" addtarget --target_name="${TARGET}"
"./${ADMIN_BINARY_NAME}" createandattach --target_name="${TARGET}" --disk_path="tmp.qcow2" --size=1000


iscsi-ls -s iscsi://${HOST_PORT}/${TARGET}
iscsi-inq iscsi://${HOST_PORT}/${TARGET}/0
iscsi-readcapacity16 iscsi://${HOST_PORT}/${TARGET}/0


TESTCASES=(
  "ALL.Inquiry.Standard"
  "ALL.Inquiry.AllocLength"
  "ALL.Inquiry.EVPD"
##  "ALL.Inquiry.BlockLimits" todo SBC-3 is required for some reason
  "ALL.Inquiry.MandatoryVPDSBC"
  "ALL.Inquiry.SupportedVPD"
  "ALL.Inquiry.VersionDescriptors"
  "ALL.Mandatory"
  "ALL.Read10.Simple"
  "ALL.Read10.BeyondEol"
  "ALL.Read10.ZeroBlocks"
  "ALL.Read10.ReadProtect"
  "ALL.Read10.DpoFua"
  "ALL.Read10.Async"
  "ALL.Read16.Simple"
  "ALL.Read16.BeyondEol"
  "ALL.Read16.ZeroBlocks"
  "ALL.Read16.ReadProtect"
  "ALL.Read16.DpoFua"
  "ALL.ReadCapacity10"
  "ALL.ReadCapacity16"
  "ALL.ReportSupportedOpcodes.Simple"
  "ALL.ReportSupportedOpcodes.OneCommand"
  "ALL.ReportSupportedOpcodes.RCTD"
  "ALL.ReportSupportedOpcodes.SERVACTV"
  "ALL.StartStopUnit.Simple"
  "ALL.StartStopUnit.PwrCnd"
  "ALL.StartStopUnit.NoLoej"
  "ALL.TestUnitReady"
  "SCSI.Write10.Simple"
  "SCSI.Write10.BeyondEol"
  "SCSI.Write10.ZeroBlocks"
  "SCSI.Write10.WriteProtect"
  "SCSI.Write10.DpoFua"
  "SCSI.Write10.Async"
  "ALL.Write16.Simple"
  "ALL.Write16.BeyondEol"
  "ALL.Write16.ZeroBlocks"
  "ALL.Write16.WriteProtect"
  "ALL.Write16.DpoFua"
  "ALL.WriteSame16.Simple"
  "ALL.WriteSame16.BeyondEol"
  "ALL.WriteSame16.ZeroBlocks"
  "ALL.WriteSame16.WriteProtect"
  "ALL.WriteSame16.Unmap"
  "ALL.WriteSame16.UnmapUnaligned"
  "ALL.WriteSame16.UnmapUntilEnd"
  "ALL.WriteSame16.UnmapVPD"
  "ALL.WriteSame16.Check"
  "ALL.WriteSame16.InvalidDataOutSize"
  "ALL.iSCSIcmdsn.iSCSICmdSnTooHigh"
  "ALL.iSCSIcmdsn.iSCSICmdSnTooLow"
#  "ALL.iSCSIdatasn" # todo fails
#   "ALL.iSCSIResiduals.Read10Invalid" # todo fails
#   "ALL.iSCSIResiduals.Read10Residuals" # todo fails
#   "ALL.iSCSIResiduals.Read16Residuals" # todo fails
#   "ALL.iSCSIResiduals.Write16Residuals" # todo fails
   "ALL.iSCSITMF.AbortTaskSimpleAsync"
   "ALL.iSCSITMF.LUNResetSimpleAsync"
   "ALL.iSCSITMF.LogoutDuringIOAsync"
#  "ALL.iSCSISendTargets.Simple" # todo hangs
#  "ALL.iSCSISendTargets.Invalid" # todo hangs
#  "ALL.iSCSINop" # todo fails
  "ALL.iSCSICHAP.Simple"
  "ALL.iSCSICHAP.Invalid"
  "ALL.MultipathIO.Simple"
  "ALL.MultipathIO.Reset"
  "ALL.MultipathIO.CompareAndWrite"
  "ALL.MultipathIO.CompareAndWriteAsync"
  "ALL.ModeSense6"
  "ALL.ModeSense6.AllPages"
  "ALL.ModeSense6.Control"
  "ALL.ModeSense6.Control-D_SENSE"
  "ALL.ModeSense6.Control-SWP"
  "ALL.ModeSense6.Residuals"
#  "SCSI.ReportLUNs.Simple" # todo test fails
##  due to incorrect remaining data size to DATA IN buffer size comparison
##  See: https://github.com/sahlberg/libiscsi/issues/385
)

declare -i success=0
declare -i failed=0
declare -i total=0
FAILED_TESTS=(
)
for test_case in "${TESTCASES[@]}";
do
	iscsi-test-cu -V -d --test="$test_case" iscsi://${HOST_PORT}/${TARGET}/0 && success=$(( success + 1 )) ||
	 failed=$(( failed + 1 ))  FAILED_TESTS+=("${test_case}")
	total=$(( total+1 ))
done

echo "================TESTS SUMMARY========"
echo "Passed: ${success}; Failed: ${failed}; Total: ${total};"
if [ $failed -ne 0 ]; then
    echo "Tests failed: "
    for test_case in "${FAILED_TESTS[@]}";
    do
      echo "${test_case}"
    done
fi

echo "================END TESTS SUMMARY========"



