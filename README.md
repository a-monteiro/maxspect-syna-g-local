# Maxspect Syna-G Local

Local Home Assistant custom integration for Maxspect Syna-G / Jump aquarium lights that speak the local Gizwits/GAgent protocol on TCP `12416`.

Status: **experimental**. Read/status is well covered; light control is intentionally limited to guarded on/off-style actions.

## What it does now

- Config flow for one or more light controller hosts.
- Local TCP probe using the observed GAgent handshake:
  - `0006` handshake
  - `0008` token acknowledgement
  - `0093` status request with APK-derived `0x12` status payload bitmap
- Decodes and exposes:
  - online/connectivity
  - mode
  - lighting phase (`auto_daylight`, `auto_lunar`, `manual_on`, `manual_off`)
  - probable lunar extension fields from the `other` block (`lunar_cycle_day`, enabled flag, high/low channel presets)
  - channel 1-6 percentages
  - schedule summary and schedule points as attributes
  - device time
  - serial number
  - identification and temperature-alert flags
  - password configured flag only; raw password bytes are never exposed
- Exposes one guarded `light` entity per controller:
  - turn on resumes the stored automatic/lunar schedule (`MODE=1`)
  - turn off writes all six manual channel outputs to zero
  - every write requires an ACK and then refreshes status from the device
- Optional/disabled diagnostic sensors expose raw collected blocks for research:
  - payload preview
  - device time hex
  - auto raw
  - display raw
  - quick-display raw
  - other raw

## Control notes

The local control payload is Maxspect/Gizwits `var_len`:

```text
0093 payload = SN(4) + 0x11 + full-schema LSB bitmap(3) + compact values in schema order
```

Live-verified examples:

```text
MODE=1 / resume auto: 000000041100000401
```

The controller appears to run lunar/night output internally after the configured schedule reaches the 20:00 all-zero point. The integration therefore exposes an inferred `lighting_phase` sensor using mode, device clock, and decoded schedule, because raw channel datapoints can still show the last daytime channel set during lunar output.

The `other` extension block also has a stable 25-byte prefix that looks lunar-related. In live captures the final byte advanced from `12` on 2026-06-08 to `13` on 2026-06-09, and both controllers now report:

```text
lunar_enabled: true
lunar_cycle_day: 13
lunar_high_channels: 100,100,100
lunar_low_channels: 30,30,30
```

These names are intentionally marked probable until confirmed against APK/UI labels or additional captures.

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
