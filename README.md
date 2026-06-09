# Maxspect Syna-G Local

Read-only Home Assistant custom integration for Maxspect Syna-G / Jump aquarium lights that speak the local Gizwits/GAgent protocol on TCP `12416`.

Status: **experimental / read-only**.

## What it does now

- Config flow for one or more light controller hosts.
- Local TCP probe using the observed GAgent handshake:
  - `0006` handshake
  - `0008` token acknowledgement
  - `0093` status request with APK-derived `0x12` status payload bitmap
- Decodes and exposes:
  - online/connectivity
  - mode
  - channel 1-6 percentages
  - schedule summary and schedule points as attributes
  - device time
  - serial number
  - identification and temperature-alert flags
  - password configured flag only; raw password bytes are never exposed
- Optional/disabled diagnostic sensors expose raw collected blocks for research:
  - payload preview
  - device time hex
  - auto raw
  - display raw
  - quick-display raw
  - other raw

It intentionally does **not** expose write/control entities yet. Basic on/off is under investigation, but the local write payload must be validated safely before it is enabled in Home Assistant.

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
