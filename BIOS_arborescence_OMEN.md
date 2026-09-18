# Arborescence BIOS/UEFI — OMEN Laptop 15-en1xxx (AMD Ryzen 7 5800H)

Transcription complète des 133 captures d'écran (`IMG_5364.jpeg` → `IMG_5496.jpeg`).

Il ne s'agit **pas** d'un "menu" au sens restauration : ce sont des captures du setup **UEFI/BIOS** de ton laptop, avec un firmware modifié type **"smokeless UMAF"** (mod communautaire AMI Aptio V qui débloque les menus cachés AMD CBS/PBS pour l'undervolt/overclock sur les laptops OMEN/Victus).

**Infos système (écran d'accueil) :**
- Modèle : OMEN Laptop 15-en1xxx
- CPU : AMD Ryzen 7 5800H with Radeon Graphics, 3.20 GHz, F.30
- RAM : 32768 MB (32 Go), 2×16 Go, DDR4 3200 MT/s (Channel A + B)
- BIOS : American Megatrends, Core Version 5.19, UEFI 2.7 / PI 1.6
- Project Version : 088D1 15.48 x64 — BIOS Date : 10/21/2025
- Stockage : SK hynix PC711 512 Go (NVMe) + Crucial CT1000T500SSD8 1 To (NVMe)

---

## 1. Écran racine (pré-setup)
`IMG_5364`
- Select Language : `<English>`
- **Device Manager** ▶
- **Boot Manager** ▶
- **Boot Maintenance Manager** ▶
- Continue
- Reset

---

## 2. Boot Manager
`IMG_5365`
Liste des périphériques de boot détectés :
- USB Drive (UEFI) – General UDisk 5.00
- Limine (×2 listés)
- Windows Boot Manager
- Windows
- Internal Hard Disk
- UEFI CT1000T500SSD8 (Crucial 1To)
- UEFI SK hynix PC711 (512 Go)
- UEFI General UDisk (clé USB)

---

## 3. Boot Maintenance Manager
`IMG_5366`
- **Boot Options** ▶
  - `IMG_5368` Go Back To Main Page / Add Boot Option ▶ / Delete Boot Option ▶ / Change Boot Order ▶
- **Driver Options** ▶
  - `IMG_5367` Go Back To Main Page / Add Driver Option ▶ / Delete Driver Option ▶ / Change Driver Order ▶
- **Console Options** ▶
  - `IMG_5369` Go Back To Main Page / Console Input Device Select ▶ / Console Output Device Select ▶ / Console Standard Error Device Select ▶ / Console Output Mode Select ▶ / COM Attribute Setup Page ▶
- **Boot From File** ▶ (File Explorer)
  - `IMG_5370` liste des volumes : clé USB (NO VOLUME LABEL) / partition NVMe (NO VOLUME LABEL, GPT)
- **Boot Discovery Policy** ▶
  - `IMG_5371` Boot Discovery Policy : `<Minimal>`
- Boot Next Value : `<NONE>`
- Auto Boot Time-out : `[65535]`

---

## 4. Device Manager (racine)
`IMG_5372`, `IMG_5496`
- **NVMe controller and Drive information** ▶
- **RAM Disk Configuration** ▶
- **AMD PBS** ▶
- **Option ROM Dispatch Policy** ▶
- **AMD CBS** ▶
- **IDE Configuration** ▶
- **PCI Subsystem Settings** ▶
- **Setup** ▶ (mène au menu Setup classique : Main/Advanced/Chipset/Security/Boot/Save & Exit)

### 4.1 NVMe controller and Drive information
`IMG_5373` → liste : SK hynix PC711 ▶ / CT1000T500SSD8 ▶

Détail par disque (`IMG_5472`, `IMG_5473`) :
| Champ | SK hynix PC711 (512 Go) | Crucial CT1000T500SSD8 (1 To) |
|---|---|---|
| Seg:Bus:Dev:Func | 00:05:00:00 | 00:06:00:00 |
| Total Size | 512.1 GB | 1000.2 GB |
| Vendor ID / Device ID | 1C5C / 174A | C0A9 / 5415 |
| Self Test Option | `<Short>` | `<Short>` |
| Self Test Action | `<Controller Only Test>` | `<Controller Only Test>` |
| Dernier résultat | Pass | Not Available |

### 4.2 RAM Disk Configuration
`IMG_5374`
- Disk Memory Type : `<Boot Service Data>`
- Create raw ▶ / Create from file ▶
- Created RAM disk list : (vide)
- Remove selected RAM disk(s) — grisé

### 4.3 AMD PBS (Platform Bios Setting — menu caché du mod)
`IMG_5375, 5376, 5380–5386` (liste continue, scroll)
- **AMD Firmware Version** ▶ (détail ci-dessous)
- SSD Power Enable : `<SSD x2>`
- GPP8/9 Select : `<PCIE>`
- HDD Power Enable : `<Enabled>`
- ODD Power Enable : `<Enabled>`
- Zero-Power ODD : `<Disabled>`
- DT Slot Power Enable : `<Enabled (x1) (Lane 0)>`
- WWAN Power Enable : `<Enabled>`
- LAN Power Enable : `<Enabled>`
- WLAN/WIFI Power Enable : `<Enabled>`
- Keep Wlan Power In S3/S4 state : `<Disabled>`
- Front Camera 0/1 Enable : `<Enabled>`
- USB Camera Enable : `<Enabled>`
- EVAL Slot Power Enable : `<Enabled>`
- Allocate 100KB for MP2 customize request : `<Auto>`
- Power Sensors Routing Select : `<WALLE lite PDT>`
- MP2 FW Selection : `<MP2_SFH>`
- EVAL CARD T-Diode Routing Select : `<EC>`
- Special Display Features : `<HybridGraphics>`
- D3Cold Support : `<Disabled>`
- NVIDIA DGPU Power Enable : `<Disabled>`
- Discrete GPU _DSM Function A : `<Disabled>`
- Discrete GPU _DSM Function B (Non-Eval) : `<Disabled>`
- Discrete GPU HPD Circuitry : `<OR Circuitry>`
- Discrete GPU's Audio : `<Keep ROM Strap Setting>`
- Discrete GPU's USB Port : `<Keep Default Setting>`
- Discrete GPU's SSID/SVID : `<Program by Vendor>`
- Discrete GPU's VGA SSID/SVID : `[0]`
- Discrete GPU's AUDIO SSID/SVID : `[0]`
- Discrete GPU BOMACO Support : `<Disabled>`
- ATCS Function 9 Support : `<Disabled>`
- ATIF Function 23 Support : `<Disabled>`
- Primary Video Adaptor : `<Int Graphics (IGD)>`
- Wake On Voice : `<Enabled>`
- ACP Power Gating : `<Disabled>`
- ACP Clock Gating : `<Enabled>`
- Above 4GB MMIO Limit : `<40bit (1TB)>`
- NVMe RAID mode : `<Disabled>`
- Touch Panel Support : `<Under I2C 0 Bus>`
- Touch Pad Support : `<Under I2C 1 Bus>`
- Nfc Support : `<Under I2C 2 Bus>`
- ALS Support : `<Under I2C 2 Bus>`
- DP0 Select : `<EDP display>`
- DP1 Select : `<DP display>`
- Turn off Xtal (S3/S5) : `<Enabled>`
- Thunderbolt Support : `<Disabled>`
- Serial Debug Message Under OS : `<Disabled>`
- Wireless LAN Recovery : `<Enabled>`
- Bluetooth PLDR support : `<Enabled>`
- Wireless Button : `<Disabled>`
- UCSI Support : `<Enabled>`
- UCSI tunnel location : `<UCSI tunnel at EC RAM>`
- Charger mode (NVDC vs BYPASS) : `<Enabled>`
- S3/Modern Standby Support : `<S3 Enable>`
- Wake on PME : `<Enabled>`
- Sensor Fusion User Mode Driver : `<Disabled>`
- MITT/WITT Selection : `<Both disable>`
- Unused GPP Clocks Off : `<Disabled>`
- Clock PM CLK_REQ0 : `<Disabled>`
- Clock PM CLK_REQ1 : `<Enabled>`
- Clock PM CLK_REQ2 : `<Enabled>`
- Clock PM CLK_REQ3 : `<Disabled>`
- Clock PM CLK_REQ4 : `<Disabled>`
- Clock PM CLK_REQ5 : `<Enabled>`
- Clock PM CLK_REQ6 : `<Enabled>`
- KBC Support : `<Enabled>`
- AcDcSwitch : `<Disabled>`
- VDDP voltage : `<0.75V>`
- VDDIO voltage : `[128]`
- VDD18 voltage : `<1.8V>`
- AMD KVM Mouse Protocol : `<Auto>`
- AMD DPTC interface : `<Disabled>`
- STT sensor reporting : `<Disabled>`
- BLINK LED : `<Enabled>`
- iLA TraceMemoryEn : `<Disabled>` (+ champ adresse `0`)

**AMD Firmware Version** (`IMG_5377–5379`, lecture seule) :
- AGESA Version : CezannePI-FP6 1.0.1.1b
- PSP BootLoader Version : 0.11.0.85
- PSP SecureOS Version : 0.11.0.85
- ABL Version : 4C176070
- APCB Version : 0000
- APOB Version : 0000
- Ucode Patch Version : A500014
- SMU FW Version : 0.64.74.0
- DXIO FW Version : 0037.0306
- MP2 FW Version : 7.0.8.13
- KVM Engine Version : 112.96.7176
- VBIOS FW Version : 113-CEZANNE-021
- GOP Driver Version : AMD GOP X64 Release Driver Rev.2.24.0.17.10.Mar 19 2024
- EC FW Version : 0CFF
- USB PD Section 1/2 FW Version : 00FF / 00FF
- TI PD FW MODE / Version : ~~~~ / D1.D1.D1.D1

### 4.4 Option ROM Dispatch Policy
`IMG_5387–5388`, `IMG_5465–5467` (identique, dupliqué aussi sous Advanced)
- AMI ROM Dispatch Policy : A5.01.20 (info)
- Restore if Failure : ☐
- Primary Video Ignore : ☑
- Device Class Option ROM Dispatch Policy (CSM inactif, 'UEFI' utilisé) :
  - Slot #32 Display Controller : ☑
  - Slot #33 Network Controller : ☑
  - Slot #50 Mass Storage Controller : ☑
  - Slot #51 Mass Storage Controller : ☑
- ⚠ Avertissement : modifier ces cases peut affecter le boot du système.

### 4.5 AMD CBS (menu caché du mod — cœur de l'overclock/undervolt)
`IMG_5389` — AMD CBS Revision Number : `0x10`
- **CPU Common Options** ▶
- **DF Common Options** ▶
- **UMC Common Options** ▶
- **NBIO Common Options** ▶
- **FCH Common Options** ▶
- **Soc Miscellaneous Control** ▶

#### 4.5.1 CPU Common Options
`IMG_5390, 5391, 5397, 5398`
- **Performance** ▶ (→ Custom Core Pstates, cf. ci-dessous)
- **Prefetcher settings** ▶
- **Core Watchdog** ▶
- RedirectForReturnDis : `<Auto>`
- Platform First Error Handling : `<Auto>`
- Core Performance Boost : `<Auto>`
- Global C-state Control : `<Auto>`
- Opcache Control : `<Auto>`
- SEV ASID Count : `<Auto>`
- SEV-ES ASID Space Limit Control : `<Auto>`
- Streaming Stores Control : `<Auto>`
- Local APIC Mode : `<Auto>`
- ACPI _CST C1 Declaration : `<Auto>`
- MCA error thresh enable : `<True>`
- MCA error thresh count : `[FF5]`
- SMU and PSP Debug Mode : `<Auto>`
- PPIN Opt-in : `<Auto>`
- Fast Short REP MOVSB : `<Enabled>`
- Enhanced REP MOVSB/STOSB : `<Enabled>`
- IBS hardware workaround : `<Auto>`

**Performance ▶ Custom Core Pstates** (`IMG_5392–5394`) :
- Écran = disclaimer AMD overclocking ("hors garantie, risque d'instabilité/dommages")
- Choix : **Decline** / **Accept** (→ Accept mène à un sous-écran vide, probablement le vrai éditeur de P-States custom par cœur, non capturé en détail)

**Prefetcher settings** (`IMG_5395`) :
- L1 Stream HW Prefetcher : `<Auto>`
- L2 Stream HW Prefetcher : `<Auto>`

**Core Watchdog** (`IMG_5396`) :
- Core Watchdog Timer Enable : `<Auto>`

#### 4.5.2 DF Common Options (Data Fabric)
`IMG_5399, 5402, 5403`
- **Scrubber** ▶
- **Memory Addressing** ▶
- CC6 memory region encryption : `<Auto>`
- Memory Clear : `<Auto>`
- Disable DF to external downstream IP SyncFloodPropagation : `<Auto>`
- Disable DF sync flood propagation : `<Auto>`
- Freeze DF module queues on error : `<Auto>`
- DF Cstates : `<Auto>`

**Scrubber** (`IMG_5400`) :
- DRAM scrub time : `<Auto>`
- Poison scrubber control : `<Auto>`
- Redirect scrubber control : `<Auto>`
- Redirect scrubber limit : `<Auto>`

**Memory Addressing** (`IMG_5401`) :
- Memory interleaving : `<Auto>`
- Memory interleaving size : `<Auto>`
- DRAM map inversion : `<Auto>`

#### 4.5.3 UMC Common Options (contrôleur mémoire)
`IMG_5404`
- **DDR4 Common Options** ▶
- **DRAM Memory Mapping** ▶
- **Phy Configuration** ▶
- **NVDIMM** ▶ (vide)
- **Memory MBIST** ▶

**DDR4 Common Options** (`IMG_5405`) :
- **DRAM Timing Configuration** ▶ → écran Accept, Overclock : `<Auto>` (`IMG_5406`)
- **DRAM Controller Configuration** ▶
- **CAD Bus Configuration** ▶
- **Data Bus Configuration** ▶
- **Common RAS** ▶
- **Security** ▶

**DRAM Controller Configuration** (`IMG_5407`) :
- **DRAM Power Options** ▶
- Cmd2T : `<Auto>`
- Gear Down Mode : `<Auto>`
- LPDDR4 Refresh Mode : `<Auto>`

  → **DRAM Power Options** (`IMG_5408`) :
  - Power Down Enable : `<Auto>`
  - Disable Burst/Postponed Refresh : `<Auto>`
  - DRAM Maximum Activate Count : `<Auto>`

**CAD Bus Configuration** (`IMG_5409`) :
- CAD Bus Timing User Controls : `<Auto>`
- CAD Bus Drive Strength User Controls : `<Auto>` (grisé)

**Data Bus Configuration** (`IMG_5410`) :
- Data Bus Configuration User Controls : `<Auto>`

**Common RAS** (`IMG_5411`) :
- Data Poisoning : `<Auto>`
- DRAM Post Package Repair : `<Disable>`
- RCD Parity : `<Disabled>`
- DRAM Address Command Parity Retry : `<Disabled>`
- Max Parity Error Replay : `[8]`
- Write CRC Enable : `<Disabled>`
- DRAM Write CRC Enable and Retry Limit : `<Disabled>`
- Max Write CRC Error Replay : `[8]`
- Disable Memory Error Injection : `<True>`
- **ECC Configuration** ▶

  → **ECC Configuration** (`IMG_5412`) :
  - DRAM ECC Symbol Size : `<Auto>`
  - DRAM ECC Enable : `<Auto>`
  - DRAM UECC Retry : `<Disabled>`

**Security** (`IMG_5413`) :
- TSME : `<Auto>`
- Data Scramble : `<Auto>`

**DRAM Memory Mapping** (`IMG_5414`) :
- Chipselect Interleaving : `<Auto>`
- BankGroupSwap : `<Auto>`
- Address Hash Bank : `<Auto>`
- Address Hash CS : `<Auto>`
- Address Hash Rm : `<Auto>`
- SPD Read Optimization : `<Enabled>`

**Phy Configuration** (`IMG_5415`) :
- **PMU Training** ▶
  - `IMG_5416` : DFE Read Training : `<Auto>` / FFE Write Training : `<Auto>`

**Memory MBIST** (`IMG_5418`) :
- MBIST Enable : `<Disabled>`
- MBIST Test Mode : `<Data Eye Mode>`
- MBIST Aggressors : `<Auto>`
- MBIST Per Bit Slave Die Reporting : `<Auto>`
- **Data Eye** ▶ (`IMG_5419–5420`) :
  - Pattern Select : `<PRBS>`
  - Pattern Length : `[6]`
  - Aggressor Channel : `<1 Aggressor Channel>`
  - Aggressor Static Lane Control : `<Disabled>`
  - Aggressor Static Lane Select (Upper/Lower 32 bits, ECC, Value) : `0` chacun
  - Target Static Lane Select ECC / Value : `0` chacun
  - Data Eye Type : `<Worst Case Margin Only>`
  - Worst Case Margin Granularity : `<Per Chip Select>`
  - Read Voltage Sweep Step Size : `<4>`
  - Read Timing Sweep Step Size : `<1>`
  - Write Voltage Sweep Step Size : `<2>`
  - Write Timing Sweep Step Size : `<1>`

#### 4.5.4 NBIO Common Options
`IMG_5421`
- IOMMU : `<Enabled>`
- DMA Protection : `<Enabled>`
- DMAr Support : `<Enabled>`
- PCIe ARI Support : `<Auto>`
- PCIe ARI Enumeration : `<Auto>`
- PSPP Policy : `<Balanced>`
- **GFX Configuration** ▶
- **Audio Configuration** ▶
- **XFR Enhancement** ▶
- **SMU Common Options** ▶

**GFX Configuration** (`IMG_5422`) :
- iGPU Configuration : `<Auto>`
- GPU Host Translation Cache : `<Auto>`

**Audio Configuration** (`IMG_5423`) :
- NB Azalia : `<Disabled>`
- Audio IOs : `<Azalia>`
- PDM Mic Selection : `<Auto>`

**XFR Enhancement** (`IMG_5424`) — écran disclaimer overclocking :
- Declined / Accepted ▶
- FCLK Frequency : `<Auto>`
- SOC OVERCLOCK VID : `[0]`
- UCLK DIV1 MODE : `<Auto>`

**SMU Common Options** (`IMG_5425, 5432`) :
- **Fan Control** ▶ → `<Auto>` (choix : Manual / Auto) (`IMG_5426`)
- **System Temperature Tracking** ▶ → STT Control : `<Auto>` (`IMG_5427`)
- **STAPM Control** ▶ (`IMG_5428–5430`) :
  - STAPM Control : `<Auto>` (choix Auto/Manual ; testé en Manual → révèle "STAPM Boost" `<Auto>`, remis en Auto ensuite)
- **SmartShift Control** ▶ → `<Auto>` (`IMG_5431`)
- System Configuration : `<Auto>` — ⚠ "peut faire planter le système selon l'OPN"
  - Choix disponibles (`IMG_5433`) : 10W POR / 15W POR / 25W POR / 35W POR / 45W POR / 54W POR (Commercial/Consumer selon le palier) / Auto
- **CPPC** ▶ (`IMG_5434`) :
  - CPPC CTRL : `<Auto>`
  - CPPC Preferred Cores : `<Auto>`
- Stability Boost : `<Auto>` (choix : Auto / Disable / Enable) (`IMG_5435`)

#### 4.5.5 FCH Common Options
`IMG_5436`
- **SATA Configuration Options** ▶
- **USB Configuration Options** ▶
- **Ac Power Loss Options** ▶
- **I2C Configuration Options** ▶
- **Uart Configuration Options** ▶
- **ESPI Configuration Options** ▶
- **XGBE Configuration Options** ▶
- **LPC Options** ▶
- **HFP Options** ▶

**SATA Configuration Options** (`IMG_5437`) :
- SATA Controller : `<Auto>`
- SATA Auto Shutdown : `<Auto>`
- Sata RAS Support : `<Auto>`
- Sata Disabled AHCI Prefetch Function : `<Auto>`
- Aggressive SATA Device Sleep Port 0/1 : `<Auto>` / `<Auto>`
- SATA0/1 port enable ▶

**USB Configuration Options** (`IMG_5438`) :
- XHCI0/1 controller enable : `<Auto>` / `<Auto>`
- USB Port0 Disable : `<Auto>`
- XHCI0/1 2.0 port enable ▶, XHCI0/1 3.1 port enable ▶

**Ac Power Loss Options** (`IMG_5439`) : Ac Loss Control : `<Previous>`

**I2C Configuration Options** (`IMG_5440`) : I2C 0/1/2 Enable : `<Auto>` ; I2C 3 Enable : `<Enabled>`

**Uart Configuration Options** (`IMG_5441`) : Uart 0/1 Enable : `<Auto>`

**ESPI Configuration Options** (`IMG_5442`) : ESPI Enable : `<Auto>`

**XGBE Configuration Options** (`IMG_5443`) : XGBE0/1 enable : `<Auto>`

**LPC Options** (`IMG_5444`) : LPC Clock Run control : `<Auto>`

**HFP Options** (`IMG_5445`) : HFP Enable : `<Auto>`

#### 4.5.6 Soc Miscellaneous Control
`IMG_5446`
- PSP RPMC Switch : `<Disabled>` (⚠ "test purpose only, NOT FOR PRODUCTION")
- ABL Console Out Control : `<Auto>`
- ABL PMU message Control : `<Auto>`

### 4.6 IDE Configuration
`IMG_5447`, `5461–5462` — écran vide (pas d'items listés)

### 4.7 PCI Subsystem Settings
`IMG_5448`, `5468`
- AMI PCI Driver Version : A5.01.20
- Above 4G Decoding : ☑
- Re-Size BAR Support : `<Disabled>`
- SR-IOV Support : ☐
- BME DMA Mitigation : ☐
- Change Settings of the Following PCI Devices (sous-liste)
- ⚠ Avertissement : peut provoquer un HANG système

---

## 5. Setup (menu BIOS classique)
`IMG_5449`
- **Main** ▶
- **Advanced** ▶
- **Chipset** ▶
- **Security** ▶
- **Boot** ▶
- **Save & Exit** ▶

### 5.1 Main
`IMG_5450–5452`
- BIOS Vendor : American Megatrends
- Core Version : 5.19 — Compliancy : UEFI 2.7 ; PI 1.6
- Project Version : 088D1 15.48 x64
- BIOS Date : 10/21/2025 16:07:47
- Access Level : Administrator
- Total Memory : 32 GB
- System Language : `<>` (vide)
- Setup mode select : `<Graphic>`
- System Date : `[09/15/2026]`
- System Time : `[14:54:21]`

### 5.2 Advanced
`IMG_5453–5459, 5463–5464, 5469–5471`
- **Trusted Computing** ▶
- **AMD fTPM configuration** ▶
- **ACPI Settings** ▶
- **SMART Settings** ▶
- **CPU Configuration** ▶
- **IDE Configuration** ▶ (vide, cf. 4.6)
- **AMI Graphic Output Protocol Policy** ▶
- **Debug Port Table Configuration** ▶
- **Option ROM Dispatch Policy** ▶ (identique à 4.4)
- **PCI Subsystem Settings** ▶ (identique à 4.7)
- **USB Configuration** ▶
- **Network Stack Configuration** ▶
- **NVMe Configuration** ▶ (identique à 4.1)
- **Demo Board** ▶

**Trusted Computing** (`IMG_5455`) :
- TPM Embedded Security Device : `<Disabled>`
- Disable Block Sid : `<Disabled>`
- "NO Security Device Found"

**AMD fTPM configuration** (`IMG_5456`) :
- AMD fTPM switch : `<AMD CPU fTPM>`
- Erase fTPM NV for factory reset : `<Enabled>`

**ACPI Settings** (`IMG_5457`) :
- Enable ACPI Auto Configuration : ☐
- Enable Hibernation : ☑
- ACPI Sleep State : `<S3 (Suspend to RAM)>`
- Lock Legacy Resources : ☐

**SMART Settings** (`IMG_5458`) :
- SMART Self Test : ☑

**CPU Configuration** (`IMG_5459`) :
- Module : CezannnCpu 06
- PSS Support : `<Enabled>`
- PPC Adjustment : `<PState 0>`
- NX Mode : `<Enabled>`
- SVM Mode : `<Enabled>`
- **Node 0 Information** ▶ (`IMG_5460`, lecture seule) :
  - AMD Ryzen 7 5800H with Radeon Graphics — 8 cœurs @ 3232 MHz, 1218 mV
  - Processor Family 19h, Model 50h-5Fh, CPUID 00A50F00
  - Vitesse max 3200 MHz / min 1200 MHz
  - Microcode Patch Level : A500014
  - Cache : L1I 32 KB/8-way, L1D 32 KB/8-way, L2 512 KB/8-way, L3 total 16 MB/16-way

**AMI Graphic Output Protocol Policy** (`IMG_5463`) :
- Codename : RENOIR, driver AMD GOP X64 Rev.2.24.0.17
- Output Select : `<LCD1_eDP>`

**Debug Port Table Configuration** (`IMG_5464`) :
- Debug Port Table : `<Disabled>`
- Debug Port Table 2 : `<Disabled>`

**USB Configuration** (`IMG_5469–5470`) :
- USB Module Version : 26
- Contrôleurs : 2 XHCIs — Périphériques : 1 Drive, 1 Keyboard, 1 Mouse
- Legacy USB Support : `<Enabled>`
- XHCI Legacy Support : `<Enabled>`
- XHCI Hand-off : `<Enabled>`
- USB Mass Storage Driver Support : `<Enabled>`
- USB transfer time-out : `<20 sec>`
- Device reset time-out : `<20 sec>`
- Device power-up delay : `<Auto>`
- General UDisk 5.00 : `<Auto>`

**Network Stack Configuration** (`IMG_5471`) :
- Network Stack : `<Enabled>`
- IPv4 PXE Support : `<Enabled>` — IPv4 HTTP Support : `<Disabled>`
- IPv6 PXE Support : `<Enabled>` — IPv6 HTTP Support : `<Disabled>`
- PXE boot wait time : `[0]`
- Media detect count : `[1]`

**Demo Board** (`IMG_5474–5475`) :
- Onboard PCIE LAN PXE ROM : `<Enabled>` (choix : Disabled / Enabled)

### 5.3 Chipset
`IMG_5476`
- **South Bridge** ▶
- **GFX Configuration** ▶
- **North Bridge** ▶

**South Bridge** (`IMG_5477`) :
- AMD Reference Code Version : Not Present
- **SB USB Configuration** ▶ (`IMG_5478`) : XHCI0/1 Port 0–3 : `<Enabled>` (×8)
- **SB Power Saving** ▶ (`IMG_5479`) : AB Clock Gating `<Auto>` / PCIB Clock Run `<Auto>`
- **SB Debug Configuration** ▶ (`IMG_5480`) :
  - **SB SATA DEBUG Configuration** ▶ (`IMG_5481–5482`) : ~15 options SATA (MAXGEN2, CLK Mode, Aggressive Link PM, Port Multiplier, Auto Clock Control, Partial State, FIS Based Switching, Command Completion Coalescing, Slumber State, MSI Capability, Target 8 Devices, Generic Mode, AHCI Enclosure, SGPIO 0) — toutes en `<Auto>`
  - **SB FUSION DEBUG Configuration** ▶ (`IMG_5483`) : Clock Interrupt Tag `<Auto>`
  - **SB MISC DEBUG Configuration** ▶ (`IMG_5484`) : SB Clock Spread Spectrum `<Auto>` / HPET In SB `<Auto>` / MsiDis in HPET `<Auto>` / _OSC For PCI0 `<Auto>` / GPP Serial Debug Bus Enable `<Auto>`

**GFX Configuration** (Chipset, `IMG_5485`) :
- IGD – AmdGop Output Priority : `<Default>`
- IGD – AmdGop Bootup Brightness Level : `[255]`

**North Bridge** (`IMG_5486`) :
- Memory Information : 32 GB
- **Socket 0 Information** ▶ (`IMG_5487`, lecture seule) :
  - Starting Address 0 KB — Ending Address 33554431 KB
  - Channel A : 16384 MB, 3200 MTs (courant/max)
  - Channel B : 16384 MB, 3200 MTs (courant/max)

### 5.4 Security
`IMG_5488–5489`
- Password Description (min 4 / max 16 caractères)
- Administrator Password / User Password (non renseignés visibles)
- **Secure Boot** ▶ (`IMG_5490`) :
  - System Mode : Setup
  - Secure Boot : `<Disabled>` / Not Active
  - Secure Boot Mode : `<Custom>`
  - Restore Factory Keys ▶ / Reset To Setup Mode ▶
  - **Key Management** ▶ (`IMG_5491–5492`) :
    - Vendor Keys : Modified
    - Factory Key Provision : `<Disabled>`
    - Restore Factory Keys ▶ / Reset To Setup Mode ▶ / Export Secure Boot variables ▶ / Enroll Efi Image ▶
    - Device Guard Ready
    - Remove 'UEFI CA' from DB ▶ / Restore DB defaults ▶
    - Table clés : Platform Key (PK), Key Exchange Keys, Authorized Signatures, Forbidden Signatures, Authorized TimeStamps, OsRecovery Signatures — toutes : Size 0, Keys 0, Key Source: No Keys

### 5.5 Boot
`IMG_5493–5494`
- Setup Prompt Timeout : `[0]`
- Bootup NumLock State : `<On>`
- Quiet Boot : ☑
- Boot Option Priorities (vide/non détecté sur cette capture)

### 5.6 Save & Exit
`IMG_5495`
- Save Options :
  - Save Changes and Exit ▶
  - Discard Changes and Exit ▶
  - Save Changes and Reset ▶
  - Discard Changes and Reset ▶
  - Save Changes ▶
  - Discard Changes ▶
- Default Options :
  - Restore Defaults ▶
  - Save as User Defaults ▶
  - Restore User Defaults ▶

---

## Notes générales
- Presque tous les réglages avancés (AMD CBS/PBS) sont sur `<Auto>` : c'est l'état par défaut du firmware modifié, rien n'a encore été personnalisé pour l'overclock/undervolt.
- Plusieurs écrans affichent "Configuration changed" en bas à droite (jaune) sur certaines captures (5429, 5450–5457, etc.) — signe que des valeurs ont été modifiées puis potentiellement pas sauvegardées (F10) avant de continuer à naviguer/photographier.
- Deux popups "Question value mismatch with Option value! Press ENTER to continue" apparaissent (`IMG_5450`, `IMG_5493`) — comportement typique d'un firmware moddé quand une variable NVRAM ne correspond plus au schéma attendu.
- Les menus clés pour l'undervolt/overclock (objectif probable du mod "smokeless") sont :
  - `AMD CBS > CPU Common Options > Performance > Custom Core Pstates` (P-States custom par cœur, écran Accept/Decline capturé mais contenu détaillé non photographié après Accept)
  - `AMD CBS > NBIO Common Options > SMU Common Options` (STAPM Control, System Configuration TDP 10W→54W, Stability Boost, CPPC, Fan Control)
  - `AMD CBS > NBIO Common Options > XFR Enhancement` (FCLK Frequency, SOC OVERCLOCK VID)
  - `AMD CBS > UMC Common Options` (timings mémoire, DRAM Power Options, ECC)
