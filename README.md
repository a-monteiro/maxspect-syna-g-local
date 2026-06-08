# Maxspect Syna-G Local

Read-only Home Assistant custom integration scaffold for Maxspect Syna-G / Jump aquarium lights that speak the local Gizwits/GAgent protocol on TCP `12416`.

Status: **experimental / read-only**.

## What it does now

- Config flow for one or more light controller hosts.
- Local TCP probe using the observed GAgent handshake:
  - `0006` handshake
  - `0008` token acknowledgement
  - `0093` status request with APK-derived `0x12` status payload bitmap
- Exposes basic diagnostic entities:
  - online/connectivity
  - last response command
  - last status payload length
  - last poll timestamp
  - error text

It intentionally does **not** write/control light settings yet.

## HACS note

HACS requires repositories to be public. Private GitHub repositories cannot be added to HACS directly. This repository is HACS-shaped so it can be made public later or copied into `/config/custom_components/maxspect_syna_g_local` manually.

## Manual install

Copy this directory into Home Assistant:

```text
custom_components/maxspect_syna_g_local
```

Then restart Home Assistant and add the integration from:

```text
Settings → Devices & services → Add integration → Maxspect Syna-G Local
```

## Development verification

```bash
python3 -m compileall -q custom_components scripts tests
python3 -m pytest -q
python3 scripts/probe_maxspect.py <device-ip-or-hostname>
```
