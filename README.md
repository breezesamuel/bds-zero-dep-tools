# bds-zero-dep-tools

Zero-dependency Python tools for hardware/industrial field work. No pip, no venv — each tool is a single file that runs on stock Python 3.

## Tools

### usb_probe.py — USB device fingerprinting (Windows)
Enumerates USB devices from the Windows registry, identifies chip vendors via a built-in VID knowledge base, and scans serial ports. Produces a structured report for asset audits and driver troubleshooting.

```
python usb_probe.py
```

### modbus_probe.py — Modbus TCP slave + master, zero dependencies
Implements Modbus TCP (FC01/02/03/04/05/06/15/16) with pure stdlib sockets. Ships with a `selfloop_proof()` that spins an in-process slave and reads it back with a master — protocol verification without any hardware. `master_read()` includes retry with length guard for short packets (real-device quirk).

```
python modbus_probe.py          # self-loop proof
python modbus_probe.py --host 192.168.1.10 read 1 0 10
```

## Why zero-dependency

Field engineers get machines they cannot install anything on. These tools run from a USB stick with the Python that is already there.

## Part of a production system

These tools are the hardware-sensing layer of a running 24/7 business system (care-tech assessments for elderly families in Shanghai): https://bigdashan.vercel.app

Also see: [PromptDeck](https://github.com/breezesamuel/promptdeck) — a one-file BYOK multi-model chat workbench.

MIT License.
