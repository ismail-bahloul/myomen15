# The raw SMU layer (HP OMEN 15-en1xxx)

`ryzen_smu` exposes two layers *below* any client — below `ryzenadj`, below the
PM table. [`access-surface.md`](access-surface.md) listed both as "reachable,
never used". This is what they do. Everything below was **read**, not written.

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

## What is *not* done, and why

Both nodes are writable and the driver will do it: `smn` takes an address-value
pair, `mp1_smu_cmd` takes any command. That is the real unlock — arbitrary SMN
registers and arbitrary SMU messages from Linux, with nothing in between.

It is left alone, for the repo's usual reason: **a control path is not used to
write before it has been read.** SMN is the SoC's internal fabric, and a
mis-addressed write there is not the same class of act as writing an EC byte
whose meaning is decoded. If this is picked up, the order is: read a *known*
register, confirm the value, and only then consider a write.

Tooling: `evidence/smuraw.py` — `mailbox`, `smn <addr>`, `version`. Read-only.

## Reproducing

```bash
sudo python3 evidence/smuraw.py mailbox
sudo python3 evidence/smuraw.py smn 0x3B10564
sudo python3 evidence/smuraw.py version
```
