@echo -off
fs1:

if not exist dumps then
  mkdir dumps
endif

echo Loading Setup-tpm-DISABLE-revert-fresh.dat (TPM enable bit back to 01 01, everything else left as the current live state)

dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -l Setup-tpm-DISABLE-revert-fresh.dat > dumps\tpm-revert-fresh-result.txt
dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -s dumps\Setup-after-revert-fresh.dat

echo done, check dumps\tpm-revert-fresh-result.txt
