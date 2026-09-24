@echo -off
fs1:

if not exist dumps then
  mkdir dumps
endif

echo Deleting AOD_SETUP (5ED15DC0-EDEF-4161-9151-6014C4CC630C) to restore the
echo pre-experiment state (the variable did not exist before this test).

dmpstore -d AOD_SETUP -guid 5ED15DC0-EDEF-4161-9151-6014C4CC630C > dumps\aod-setup-revert-result.txt
dmpstore AOD_SETUP -guid 5ED15DC0-EDEF-4161-9151-6014C4CC630C -all > dumps\aod-setup-after-revert.txt

echo done, check dumps\aod-setup-revert-result.txt.
echo dumps\aod-setup-after-revert.txt should report "No matching variables found".
