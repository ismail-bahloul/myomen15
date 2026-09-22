@echo -off
fs1:

if not exist dumps then
  mkdir dumps
endif

echo Loading Setup-tpm-ENABLE-test.dat (TPM enable bit, offsets 3-4, 01 01 -> 00 00)

dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -l Setup-tpm-ENABLE-test.dat > dumps\tpm-apply-result.txt
dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -s dumps\Setup-after-apply.dat

echo done, check dumps\tpm-apply-result.txt and dumps\Setup-after-apply.dat
echo Now reboot into the BIOS setup (do not save anything) and look at
echo TPM Embedded Security Device -- it should read Enabled.
echo Then come back to this key and run tpm-revert-disable.nsh
