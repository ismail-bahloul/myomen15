@echo -off
fs1:
echo Phase 1: dumping the BIOS setup variables to dumps

if not exist dumps then
  mkdir dumps
endif

dmpstore -all -s dumps\all-preboot.dat
dmpstore -all > dumps\all-preboot-console.txt

dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -s dumps\Setup.dat
dmpstore SetupDefault -guid 0EE72C08-8185-427A-A58A-855B78B7BA0B -s dumps\SetupDefault.dat
dmpstore StdDefaults -guid 4599D26F-1A11-49B8-B91F-858745CFF824 -s dumps\StdDefaults.dat
dmpstore AmdSetup -guid 3A997502-647A-4C82-998E-52EF9486A247 -s dumps\AmdSetup.dat
dmpstore AMD_PBS_SETUP -guid A339D746-F678-49B3-9FC7-54CE0F9DF226 -s dumps\AMD_PBS_SETUP.dat
dmpstore HPSetupData -guid 206BC44A-C8A7-4000-896F-0DA25FB37702 -s dumps\HPSetupData.dat
dmpstore NewHPSetupData -guid 206BC44A-C8A7-4000-896F-0DA25FB37702 -s dumps\NewHPSetupData.dat
dmpstore AMITSESetup -guid C811FA38-42C8-4579-A9BB-60E94EDDFB34 -s dumps\AMITSESetup.dat

echo phase 1 done, files are in dumps on this USB key
echo Do NOT run a script for phase 2, see phase2-writeback-test.txt and type
echo each command by hand at the Shell prompt.
