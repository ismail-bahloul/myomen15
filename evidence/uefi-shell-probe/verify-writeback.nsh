@echo -off
fs1:

if not exist dumps then
  mkdir dumps
endif

echo Phase 2: writing Setup back with its own unchanged bytes

dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -s dumps\Setup-preloop.dat
dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -l dumps\Setup-preloop.dat > dumps\writeback-result.txt
dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -s dumps\Setup-postloop.dat

echo phase 2 done, check dumps\writeback-result.txt for the real answer
