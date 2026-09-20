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

## The protocol, verified end to end

Sending a command: write the six u32 arguments to `smu_args`, write the command
to `mp1_smu_cmd`, then read the response code from the same node. The codes are
the driver's own: `0x01` OK, `0xFF` failed, `0xFE` unknown command, `0xFD`
rejected-prereq, `0xFC` rejected-busy, and so on.

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

Tooling: `evidence/smuraw.py` — `mailbox`, `smn <addr>`, `version`, `pmver`,
`drambase`, `stapmtest`.

## Reproducing

```bash
sudo python3 evidence/smuraw.py mailbox
sudo python3 evidence/smuraw.py smn 0x3B10564
sudo python3 evidence/smuraw.py version
sudo python3 evidence/smuraw.py pmver
sudo python3 evidence/smuraw.py drambase
sudo python3 evidence/smuraw.py stapmtest
```
