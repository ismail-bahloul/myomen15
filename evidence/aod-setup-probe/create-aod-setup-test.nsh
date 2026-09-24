@echo -off
fs1:

if not exist dumps then
  mkdir dumps
endif

echo Creating AOD_SETUP (5ED15DC0-EDEF-4161-9151-6014C4CC630C) -- currently absent.
echo This variable gates AodSmmSsp's entire SMI command dispatcher (see
echo ../aod-setup-probe/README.md): if GetVariable("AOD_SETUP", ...) fails,
echo the handler returns before testing any command, including Set PPT Limit
echo and Set Curve Optimizer. Today it always fails, because the variable does
echo not exist. This creates it with a single 0x01 byte, NV+BS+RT.

dmpstore AOD_SETUP -guid 5ED15DC0-EDEF-4161-9151-6014C4CC630C -l aod-setup-create.dat > dumps\aod-setup-create-result.txt
dmpstore AOD_SETUP -guid 5ED15DC0-EDEF-4161-9151-6014C4CC630C -s dumps\AOD_SETUP-after-create.dat

echo done, check dumps\aod-setup-create-result.txt and dumps\AOD_SETUP-after-create.dat
echo Reboot into Linux and rerun the Set PPT Limit test from
echo evidence/aod-power-limit-probe.txt to see whether the \AOD road is still
echo inert now that the gate variable exists.
echo To revert: run revert-aod-setup.nsh from this key.
