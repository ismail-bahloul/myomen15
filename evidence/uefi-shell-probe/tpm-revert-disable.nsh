@echo -off
fs1:

if not exist dumps then
  mkdir dumps
endif

echo Loading Setup-tpm-DISABLE-revert.dat (TPM enable bit, offsets 3-4, back to 01 01)

dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -l Setup-tpm-DISABLE-revert.dat > dumps\tpm-revert-result.txt
dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -s dumps\Setup-after-revert.dat

echo done, check dumps\tpm-revert-result.txt and dumps\Setup-after-revert.dat
echo Reboot into the BIOS setup once more (do not save anything) and confirm
echo TPM Embedded Security Device reads Disabled again.
