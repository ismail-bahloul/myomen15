# The HP NVRAM layer — the two HP GUIDs

`efi-nvram.md` catalogues the variables that hold the *setup* (the `Setup`,
`AmdSetup`, `AMD_PBS_SETUP` store). This is the **other half**: HP's own state,
in two vendor GUIDs that have nothing to do with the AMD/AMI setup store. Both
were read at runtime on this machine; nothing here is a menu option.

## `0ee72c08-8185-427a-a58a-855b78b7ba0b` — HP config / command layer

**42 variables.** This GUID is *also* the `SetupDefault` GUID, so it is the
namespace HP uses for everything around the setup. Grouped:

| Group | Variables |
|---|---|
| UI hiding | `HideCdromBootOption`, `HideFanAlwaysOn`, `HpShowSpareKeyItem`, `HPSpareKey` (198 B) |
| Security / TPM | `PreviousSecureBoot`, `PreviousTpmDevice`, `DisplayTpmMsg`, `PostTpmDetect`, `TpmStateFlag`, `ResetSecurityPending`, `PlatformKey`, `HPSignFlag`, `PspNvramClearCount` |
| Boot | `FixedBootNum`, `UefiFixedBootNum`, `HPSkipBUCountdown`, `TimeOutDefault`, `PlatformLangDefault` |
| Command channels | `HpBiosUpdCommand`, `HpBiosUpdStatus0/1`, `HpSysDiagCommand`, `HpSysDiagStatus`, `FactoryCmdData`, `FactoryCmdStatus`, `FeatureByteFlag`, `CleanNvram`, `ClearEventLog` |
| Module IDs | `BTModuleID`, `ComboBTModuleID`, `WiMAXModuleID`, `SpeakerID`, `PannelEDID` |
| Misc | `OOBE`, `PinLoadDefaults`, `RtcLostPower`, `MPMUnlock`, `WindowsToGo`, `MSFTDebugPolicy`, `OEMDeviceStatus`, `SetupDefault`, `PendingAction` |

**22 of these are declared as IFR varstores in the `Setup` module** — the
formally-named subset: `OEMDeviceStatus`, `Hide*`, `TpmStateFlag`,
`HpBootOrder`, `FixedBootNum`, `UefiFixedBootNum`, `MPMUnlock`, `WindowsToGo`,
`MSFTDebugPolicy`, `PendingAction`, `PlatformKey`, `GOPCount`, `NewSystemFamily`,
`RtcLostPower`-adjacent flags. The rest are not in any IFR — HP firmware/agent
writes them directly.

## `206bc44a-c8a7-4000-896f-0da25fb37702` — HP data blobs

**5 variables, none declared in any IFR** (checked across the whole dump):

| Variable | Size | Content |
|---|---|---|
| `HPSetupData` | 116 B | HP's own setup blob (mirrored in flash) |
| `NewHPSetupData` | 1024 B | the staged/pending copy (same header, larger buffer) |
| `HPAmiTse` | 65 B | AMI TSE state (all-zero here) |
| `HPPlatformLang` | 6 B | HP's language preference |
| `HPTimeout` | 2 B | HP's POST timeout |

`HPSetupData`/`NewHPSetupData` begin with the same 8-byte header
(`01 00 00 00 00 00 00 00`) then an id/value list (`… 01 00 02 00 03 00 … 05 00`),
consistent with a *current* vs *pending* pair committed on save.

## Where they come from

- The `0ee72c08` GUID is declared by the `Setup` module's IFR (22 varstores).
- The `206bc44a` names are referenced by AMI's NVRAM drivers — `NvramDxe`
  (module 379) and `NvramSmm` (180) — and by HP's own `OememDxe` (module 1),
  which also references `OEMDeviceStatus`, `HpSystemFamily`, `HPC_SUPPORT`.

## Not a lever

**All 47 variables are locked from Linux** (`O_RDWR` refused — the same
`efivarfs` immutability as the setup store; see
[`firmware-limits.md`](../../firmware-limits.md#correction-the-setup-lock-is-linuxs-not-the-firmwares)).
Several are *command channels* (`HpBiosUpdCommand`, `HpSysDiagCommand`,
`FactoryCmdData`) — which is exactly what one would want to poke — and they are
precisely the guarded set. None of it is a power or performance lever.

## For the record

`PspNvramClearCount` ties into the PSP work ([`psp-campaign.md`](../../psp-campaign.md));
`PannelEDID` stores the panel's EDID; `MPMUnlock` is the manufacturing-mode
unlock; `HPSkipBUCountdown` relates to the BIOS-update countdown.
