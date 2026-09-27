# The firmware gate, observed: a tampered TA is refused

Everything so far in this campaign is **static**: the verifier was read, its
constants checked, its callers swept. [`psp-boot-verifier.md`](psp-boot-verifier.md)
and [`psp-tee-runtime.md`](psp-tee-runtime.md) concluded that the firmware gate is a
correct RSA-2048/SHA-256 PKCS#1 v1.5 check — but *concluded*, from code. This page
does the thing the repo asks for (**measure, do not assume**): it exercises the one
verifier the OS can actually reach, and watches the PSP reject a modified blob.

It is not a bug hunt. It is a **validation of the model** — and it holds.

## The one path the OS can drive

The `amdtee` driver loads a Trusted Application as **firmware**, and the PSP
verifies it ([`psp-tee.md`](psp-tee.md)). So a single ioctl reaches the verifier
with bytes the host chose:

```
open("/dev/tee0") + TEE_IOC_OPEN_SESSION(uuid)
  -> amdtee_open_session -> request_firmware("amdtee/<uuid>.bin")
  -> copy_ta_binary -> TEE_CMD_LOAD_TA (the mapped blob) -> the PSP verifies it
  -> ret (the PSP's verdict) comes back in tee_ioctl_open_session_arg.ret
```

The harness is [`evidence/psp-tee-empirical/teeopen.c`](evidence/psp-tee-empirical/teeopen.c)
(a `TEE_IOC_OPEN_SESSION` against an AMD-TEE TA). Three details it had to get right,
each a small finding in itself:

- the driver accepts only `TEE_IOCTL_LOGIN_PUBLIC` (`LOGIN_USER` is rejected with
  `unsupported client login method`);
- `/dev/tee0` takes the UUID in **GP/RFC-4122 mixed-endian** form — the first three
  fields are byte-swapped before the driver prints the firmware name, so the bytes
  for `773bd96f-b83f-4d52-b12dc529b13d8543` start `6f d9 3b 77 …`;
- the kernel **re-reads the firmware from disk on every open** (no cache): removing
  the file yields `failed to load firmware … error -2`, so a byte-flip on disk is
  what the PSP actually sees.

## The experiment

The target is the AMD PMF TA, `amdtee/773bd96f-b83f-4d52-b12dc529b13d8543.bin.zst`,
decompressed 12864 bytes laid out as header `[0x000..0x100]`, signed body
`[0x100..0x3140]`, signature `[0x3140..0x3240]`. For each variant we flip **one**
byte (XOR 0xff), install it under the TA's real UUID, open a session, and read the
PSP's `ret`. Full run: [`evidence/psp-tee-empirical/run.sh`](evidence/psp-tee-empirical/run.sh),
captured output [`evidence/psp-tee-empirical/results.txt`](evidence/psp-tee-empirical/results.txt).

| variant | PSP `ret` |
|---|---|
| **pristine** | **`0x33`** |
| prefix byte `@0x00` | `0x34` |
| header byte `@0x40` | `0x34` |
| body byte `@0x1000` | `0x34` |
| body byte `@0x3000` | `0x34` |
| signature byte `@0x3200` | `0x34` |

Every single-byte change, anywhere in the module — including the 16-byte zero prefix
before `$PS1` and a byte inside the **signature itself** — moves the verdict from
`0x33` to `0x34`.

## What it shows

**A single flipped byte is detected, before anything runs.** The `0x34` is not the
pristine refusal: were the integrity check *downstream* of whatever produces the
pristine `0x33`, a tampered blob would also have stopped at `0x33`. It does not; it
stops at a **distinct** code. So the whole-module integrity/signature verification
runs **before** the `0x33` decision, and tampering fails it. That is exactly what
the static reading of `FUN_00016748`/`FUN_00013570` predicted — now observed on
silicon, on the only path the OS can drive.

It also shows the scope of the check: a byte in the header, the body, or the
signature is all covered. The signed region is the whole module, as the boot
loader's `psptool` finding said (the signature is over the **stored** bytes).

## What it does not show (the honest part)

- **The pristine TA was refused too (`0x33`).** We never got an *accept* baseline.
  So the demonstration is a **differential** (pristine `0x33` → tampered `0x34`),
  not "accept vs. refuse". The `0x33` is a later, platform-level refusal: on this
  machine even the vendor TA does not load from the OS, which is consistent with
  the TEE ACPI being broken at boot —
  `ACPI Error: Aborting method \TAAD.RTWT … (AE_NOT_EXIST)` — the `\TAAD` device
  the TEE world needs is not provisioned. That is its own result: **the OS-reachable
  TA path does not reach acceptance on this machine**, independent of the signature.
- It exercises the **TA** verifier, not the BIOS/SMU verifier directly — the OS
  cannot feed a BIOS image to the PSP. But it is the same verifier family, on the
  host-reachable path, and the static work tied the TA loader (`FUN_00016748`) and
  the PKCS#1 verifier (`FUN_00013570`) together.

## Machine state

Fully reversible and restored: the firmware was backed up and the original md5
(`02db88091de538da518bfd8afd61cf67`) is back in place, the extra file was removed,
and `amdtee` is unloaded (`/dev/tee0` gone). The only lasting change is this page.

## Reproducing

```bash
sudo modprobe amdtee
gcc -O2 -Wall -o evidence/psp-tee-empirical/teeopen evidence/psp-tee-empirical/teeopen.c
sudo sh evidence/psp-tee-empirical/run.sh        # prints the table, restores the file
sudo rmmod amdtee
```

## Related

- [`psp-tee-runtime.md`](psp-tee-runtime.md) — the runtime verifier and the TA loader `FUN_00016748` this exercises.
- [`psp-tee.md`](psp-tee.md) — the AMD-TEE door (`amdtee` → `/dev/tee0`) and the TAs as `$PS1` firmware files.
- [`psp-boot-verifier.md`](psp-boot-verifier.md) — the signature-over-stored-bytes design this confirms.
