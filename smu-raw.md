# The raw SMU layer (HP OMEN 15-en1xxx)

`ryzen_smu` exposes two layers *below* any client — below `ryzenadj`, below the
PM table. [`access-surface.md`](access-surface.md) listed both as "reachable,
never used". This is what they do.

Update: the mailbox *is* now written to — two query-class commands sent and
cross-checked, then one that actually mutates state (`SetStapmLimit`, the same
command `ryzenadj` already sends routinely on this machine). `smn` writes are
still untouched; see "What is written now, and what still isn't" below.

## The nodes

| Node | Mode | Meaning |
|---|---|---|
| `smn` | rw | read/write one 32-bit SMN register |
| `smu_args` | rw | 6 × u32 command arguments |
| `mp1_smu_cmd` | rw | send an MP1 command (write) / last response (read) |
| `rsmu_cmd` | rw | the same, for the RSMU mailbox |

Reading an SMN register: write the address as one u32, read one u32 back.
Writing one: write two u32, `(address, value)`. **Only reads were used here.**

## The same SMN, without the module

The driver reaches SMN through the standard AMD indirect window on the root
complex `00:00.0`: offset `0xB8` is the SMN index, `0xBC` is the data. That is
a plain PCI config register, so the *same* reads are available with `setpci`
and no `ryzen_smu` at all:

```
$ sudo setpci -s 00:00.0 b8.l=3B10A80     # write the SMN address
$ sudo setpci -s 00:00.0 bc.l             # read the data back
00000001
$ sudo python3 evidence/smuraw.py smn 0x3B10A80
SMN 0x03B10A80 = 0x00000001  (OK)
```

Cross-checked over the whole `0x3B10000`–`0x3B10FFF` mailbox page, both ways
(`evidence/smnscan.py diff`): **1021 of 1024 registers agree exactly**. The
three that differ are volatile — `0x3B10F00` changes on *every* read, so it
has a read side-effect, and `0x3B10F14` / `0x3B1002C` flip between reads. That
is itself worth keeping: **an SMN read is not guaranteed to be idempotent**,
which is one more reason a blind SMN write sweep is the wrong first move.

Two consequences:

- SMN is reachable from a running OS with no kernel module — `setpci` alone is
  enough. The module is a convenience, not the gate.
- The page maps cleanly: MP1 `cmd 0x3B10528` / `rsp 0x3B10564` /
  `args 0x3B10998`, RSMU `cmd 0x3B10A20` / `rsp 0x3B10A80` / `args 0x3B10A88`,
  and the SMU version `0x00404A00` at `0x3B10058` — all matching what the
  driver and `ryzenadj` already report. Full non-zero map:
  `evidence/deep-recon/smn-mailbox-page.txt`.

The window is **read/write** — `0xB8`/`0xBC` accepts a write exactly as the
sysfs node's two-`u32` form does. Detected, not used: the position on `smn`
writes below applies to this path identically.

## The protocol, verified end to end

Sending a command: write the six u32 arguments to `smu_args`, write the command
to `mp1_smu_cmd`, then read the response code from the same node. The codes are
the driver's own: `0x01` OK, `0xFF` failed, `0xFE` unknown command, `0xFD`
rejected-prereq, `0xFC` rejected-busy, and so on.

**That last step was wrong, and this section used to assert it.** The response
node does *not* report the code faithfully — it reports `0x01` for a `Failed`.
See "The response node masks failures" below; the true code has to be read from
the rsp register over `smn`.

`GetSmuVersion` — command `0x02`, the one the driver itself sends at init, so a
known-good query:

```
$ sudo python3 evidence/smuraw.py version
MP1 cmd 0x02 (GetSmuVersion): rsp 0x01 (OK)
  reply in smu_args[0] : 0x00404A00
  reply in smu_args    : 0x00404A00 0x00000000 0x00000000 0x00000000 0x00000000 0x00000000
  sysfs version        : 64.74.0
```

`0x00404A00` = `(64 << 16) | (74 << 8) | 0` — the version, matching the sysfs
node exactly. The whole path works from userspace.

## The mailbox, live

The mailbox registers are themselves readable through SMN, which is what makes
the layer verifiable:

```
MP1  cmd 0x3B10528 = 0x21    rsp 0x3B10564 = 0x01 (OK)   args0 0x3B10998 = 0x55F0
RSMU cmd 0x3B10A20 = 0x65    rsp 0x3B10A80 = 0x01 (OK)
```

Two cross-checks fall straight out of it:

- `args0 = 0x55F0 = 22000` is exactly the `--apu-slow-limit=22000` of this
  machine's own AC profile — the raw register agrees with the configuration.
- `RSMU cmd = 0x65` is `TransferTableSmu2Dram`, the Cezanne PM-table refresh
  (the driver's own `fn` for this codename), and it answers OK.

Cezanne mailbox addresses (MP1 interface v12, from the driver's codename table):

```
MP1   cmd 0x3B10528   rsp 0x3B10564   args 0x3B10998
RSMU  cmd 0x3B10A20   rsp 0x3B10A80   args 0x3B10A88
```

## Two more commands, sent for the first time

`GetSmuVersion` was the only command ever sent — the one the driver issues
itself at init. Two more, both taken from Cezanne's own `case` in
`/usr/src/ryzen_smu-*/smu.c` (not guessed), both query-class:

```
$ sudo python3 evidence/smuraw.py pmver
RSMU cmd 0x06 (GetPmTableVersion): rsp 0x01 (OK)
  args back : 0x00400005 0x00000000 0x00000000 0x00000000 0x00000000 0x00000000
  sysfs pm_table_version : 0x00400005
  MATCH

$ sudo python3 evidence/smuraw.py drambase
RSMU cmd 0x66 (GetDramBaseAddress): rsp 0x01 (OK)
  args back : 0xB6AE6000 0x00000000 0x00000000 0x00000000 0x00000000 0x00000000
  DRAM base address : 0x00000000B6AE6000
```

Both cross-check against something independent of the command itself:
`GetPmTableVersion`'s reply matches the driver's own `pm_table_version` sysfs
node exactly, and `GetDramBaseAddress`'s reply (`0xB6AE6000`) lands inside a
region `/proc/iomem` marks `Reserved` (`b698d000-b6b0bfff`) — not a plausible
coincidence for a made-up address. Both commands: no crash, no hang, nothing
to revert.

## A real write: `SetStapmLimit`, and getting it back

`ryzenadj --stapm-limit=N` is one of this machine's most-used levers — the
whole power-profile setup in `firmware-limits.md` depends on it, watched and
re-applied within 0.12 s of any drift. Its Cezanne implementation, in
RyzenAdj's own `lib/api.c` (`set_stapm_limit`), is exactly one command: `MP1
cmd 0x14`, `arg0 = value in mW`. Sent from this repo's own script instead of
the `ryzenadj` binary, self-restoring, with the running `power-profile-watch`
service left active the whole time:

```
$ sudo python3 evidence/smuraw.py stapmtest
baseline STAPM limit : 35000 mW
writing MP1 cmd 0x14 (SetStapmLimit) arg0=40000 ...
  rsp = 0x01 (OK)
  STAPM limit immediately after : 40000 mW
  MATCH
restoring baseline MP1 cmd 0x14 arg0=35000 ...
  rsp = 0x01 (OK)
  STAPM limit after restore : 35000 mW
  RESTORED
```

Two confirmations that this isn't a fluke: `ryzenadj --info` (a process this
script never touches) shows the changed value immediately, and — run once
without the script's own restore, separately — `power-profile-watch` caught
the drift and reverted it to `35000` on its own within 0.8 s, exactly the
mechanism `firmware-limits.md` already documents. The raw sysfs path and
`ryzenadj`'s own path are provably the same mailbox, the same command, the
same effect.

## The response node masks failures

Everything above read the response code back from `mp1_smu_cmd` itself. **That
node does not report the code faithfully: it reports `0x01` for any non-OK code
that arrives before the driver's retry counter runs out.** From the driver's own
`smu_send_command()` (`/usr/src/ryzen_smu-*/smu.c`):

```c
do
  read rsp -> tmp
while (tmp == 0 && retries--);

if (tmp != SMU_Return_OK && !retries) { ...; return tmp; }
return SMU_Return_OK;
```

The SMU answers a rejected command in microseconds, so the loop exits with
`retries` still non-zero, the `!retries` guard is false, and the function falls
through to `return SMU_Return_OK`. A `0xFF Failed` comes back out of the node as
`0x01 OK`. Nothing in `smuraw.py` caught it, because every command that script
sends is, in fact, OK.

The truth lives in the **rsp register**, readable through `smn` (MP1
`0x3B10564`, RSMU `0x3B10A80`). `evidence/smu-gate-probe.py` reads both and
prints them side by side, so the masking is visible rather than assumed.

## Is the Curve Optimizer gate a transport problem? Measured: no

With the masking lifted, the gate has a shape. The SMU distinguishes a command
it does not know (`0xFE UnknownCmd`) from one it knows and refuses (`0xFF
Failed`). Sending deliberate garbage IDs and then the CO family gives:

```
invalid 0xEE / 0x7E / 0x99 / 0xAB (MP1)            -> 0xFE UnknownCmd
invalid 0xEE / 0x7E (RSMU)                         -> 0xFE UnknownCmd
set-coall 0x55 / set-coper 0x54 / set-cogfx 0x64   -> 0xFF Failed
```

The CO commands answer `Failed`, **not** `UnknownCmd`. The firmware therefore
*implements and recognises* them and refuses them on purpose — a policy, not a
missing command, and not a transport an OS client could route around. This is
the raw mailbox's own statement of what `firmware-limits.md` concluded from
`ryzenadj` and UXTU, now down to the exact status codes.

Consequence for the one remaining road: `\AOD`/SMM
([`firmware-limits.md`](firmware-limits.md#the-second-road-measured-it-is-inert))
does not send this mailbox message at all — it pokes SMM. A gate that
*recognises* the command and refuses it reads naturally as a firmware policy
that is independent of who is asking, which makes an SMM bypass less likely. It
does not prove it: the SMM road is still untried, and this measurement does not
speak for it.

The CO commands were sent here only with argument `0`
(`EncodeCurveOptimiserOffset(0) == 0`, "offset zero") — a no-op whatever the
SMU decides. Nothing moved: `ryzenadj --info` is unchanged and `GetSmuVersion`
still answers. Raw log:
[`evidence/smu-gate-probe.log`](evidence/smu-gate-probe.log).

## What is written now, and what still isn't

Sending a command **is** a write — six `u32`s to `smu_args`, one `u32` to
trigger it — and one of the four commands sent so far (`SetStapmLimit`)
genuinely mutates SMU state, not just queries it. What makes it safe enough to
run: it is not a new, unverified command. It is a command whose exact effect
was already independently known (from `ryzenadj`'s own source and this
machine's own months of routine use of it) before it was ever sent from this
script.

Left alone, still: `smn` writes — a raw address-value poke into the SoC's
internal fabric, with no per-command validation the way a mailbox message
gets — and any mailbox command whose effect *isn't* already known from an
independent source the way `SetStapmLimit`'s was. SMN is a different class of
act from a decoded EC byte or a documented mailbox command: there is no
equivalent of "read a known register, confirm the value" to de-risk a write,
because a wrong SMN address isn't a register with a known meaning to check
against first.

One named reason to *want* an SMN write is now closed from the other side. The
Curve Optimizer gate this page measured (`0xFF Failed`) lives in an SMU-internal
config bit, and that bit's source register sits **outside the host's SMN window**
— `0x115d64c` reads `0` from the host while `0x3B10058` returns the SMU version.
So for the one target that mattered, the write is not merely un-de-risked: the
address is not the host's to write, and the bit is consumed before the host runs.
See [`psp-firmware.md`](psp-firmware.md), and §7 of
[`evidence/psp-firmware/curve-optimizer-handler.txt`](evidence/psp-firmware/curve-optimizer-handler.txt).

Tooling: `evidence/smuraw.py` — `mailbox`, `smn <addr>`, `version`, `pmver`,
`drambase`, `stapmtest`; and `evidence/smu-gate-probe.py` — `controls`, `gate`,
`all` (the masking correction, and the gate discriminator above).

## Reproducing

```bash
sudo python3 evidence/smuraw.py mailbox
sudo python3 evidence/smuraw.py smn 0x3B10564
sudo python3 evidence/smuraw.py version
sudo python3 evidence/smuraw.py pmver
sudo python3 evidence/smuraw.py drambase
sudo python3 evidence/smuraw.py stapmtest

# the response-node masking, and the CO gate's true status codes
sudo python3 evidence/smu-gate-probe.py all
```
