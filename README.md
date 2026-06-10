# Maxspect Syna-G Local

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://www.hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.6%2B-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Local Home Assistant custom integration for Maxspect Syna-G / Jump aquarium lights that speak the local Gizwits/GAgent protocol on TCP `12416`.

Status: **experimental but live-tested**. Read/status support is broad; writes are deliberately explicit and guarded.

## Features

- Config flow for one or more light controller hosts.
- Local TCP polling; no vendor cloud required.
- One Home Assistant device per controller.
- Connectivity/status binary sensor.
- Main `light` entity per controller:
  - turn on resumes automatic/lunar schedule (`MODE=1`)
  - turn off is intentionally safe and does **not** zero outputs
- Manual channel number entities, 0-100%, labelled with observed APK names:
  - Purplish Blue
  - Pool Blue
  - Royal Blue + Cool White
  - Green
  - Warm White
  - Red
- Lunar controls:
  - enable/disable lunar flag
  - lunar cycle day
  - high channel triplet
  - low channel triplet
- Automatic schedule sensors with decoded points.
- Schedule backup/restore services and per-controller buttons.
- Explicit action buttons:
  - resume automatic schedule
  - manual all channels off
  - sync device time
  - backup automatic schedule
  - restore backed-up schedule
- Optional diagnostic raw-block sensors for protocol research.

## Installation with HACS

This is a custom repository, not a default HACS repository.

1. Open Home Assistant.
2. Go to **HACS → Integrations**.
3. Open the three-dot menu and choose **Custom repositories**.
4. Add this repository URL:

   ```text
   https://github.com/a-monteiro/maxspect-syna-g-local
   ```

5. Select category **Integration**.
6. Install **Maxspect Syna-G Local**.
7. Restart Home Assistant.
8. Add the integration from:

   ```text
   Settings → Devices & services → Add integration → Maxspect Syna-G Local
   ```

## Manual installation

Copy the integration directory into Home Assistant:

```text
custom_components/maxspect_syna_g_local
```

Then restart Home Assistant and add the integration from:

```text
Settings → Devices & services → Add integration → Maxspect Syna-G Local
```

## Configuration

The config flow asks for one or more controller hosts.

Requirements:

- Home Assistant must be able to reach each light controller on TCP port `12416`.
- The controller must already be paired/configured by the official app or existing local setup.
- Static DHCP reservations or stable hostnames are recommended.

## Entities

Entity IDs depend on Home Assistant's entity registry, but each configured controller exposes the following entity types.

### Light

- Main controller light entity.
- `turn_on`: resumes automatic/lunar schedule.
- `turn_off`: safe no-op/refresh by design; use the explicit all-off button or service if you really want manual zero output.

### Numbers

Manual channel sliders:

- Channel 1: Purplish Blue
- Channel 2: Pool Blue
- Channel 3: Royal Blue + Cool White
- Channel 4: Green
- Channel 5: Warm White
- Channel 6: Red

Lunar sliders:

- Lunar cycle day, 0-29
- Lunar high blue/white/moon, 0-100%
- Lunar low blue/white/moon, 0-100%

### Switches

- Lunar enabled flag.

### Sensors

- Mode
- Lighting phase
- Channel percentages
- Automatic schedule summary and points
- Lunar enabled
- Lunar cycle day
- Lunar high channels
- Lunar low channels
- Device time
- Serial number
- Identification / alert flags
- Optional disabled diagnostic raw blocks

### Buttons

- Resume automatic schedule
- Manual all channels off
- Sync device time
- Backup automatic schedule
- Restore backed-up schedule

## Services

### `maxspect_syna_g_local.apply_manual_preset`

Apply a six-channel manual preset to one device or all configured devices.

Example:

```yaml
service: maxspect_syna_g_local.apply_manual_preset
data:
  device: aquarium-light-1
  channel_1: 65
  channel_2: 65
  channel_3: 65
  channel_4: 0
  channel_5: 5
  channel_6: 0
```

Omit `device` to apply to all configured controllers.

### `maxspect_syna_g_local.backup_schedule`

Persist the current raw automatic schedule block for one device or all configured devices.

```yaml
service: maxspect_syna_g_local.backup_schedule
data:
  device: aquarium-light-1
```

### `maxspect_syna_g_local.restore_schedule`

Restore the last backed-up raw automatic schedule block.

```yaml
service: maxspect_syna_g_local.restore_schedule
data:
  device: aquarium-light-1
```

This writes configuration back to the light. Use deliberately.

### `maxspect_syna_g_local.apply_lunar_config`

Apply known lunar fields while preserving the rest of the raw extension block byte-for-byte.

```yaml
service: maxspect_syna_g_local.apply_lunar_config
data:
  device: aquarium-light-1
  enabled: true
  cycle_day: 14
  high_channels: [100, 100, 100]
  low_channels: [30, 30, 30]
```

All fields except `device` are optional; omitted fields are preserved from current device state.

## Safety model

This integration intentionally avoids surprising aquarium light changes.

- Normal `light.turn_off` does not zero the channels.
- Potentially disruptive writes are explicit buttons or services.
- Schedule restore writes the exact raw backed-up schedule block, not a reconstructed approximation.
- Lunar updates modify only known lunar bytes and preserve unknown extension bytes.
- Every write requires a device ACK and then refreshes status.

## Protocol notes

The local control payload uses the Maxspect/Gizwits `var_len` form:

```text
0093 payload = SN(4) + 0x11 + full-schema LSB bitmap(3) + compact values in schema order
```

Live-verified example:

```text
MODE=1 / resume auto: 000000041100000401
```

The controller appears to run lunar/night output internally after the configured schedule reaches the all-zero evening point. The integration therefore exposes an inferred `lighting_phase` sensor using mode, device clock, and decoded schedule, because raw channel datapoints can still show the last daytime channel set during lunar output.

## Troubleshooting

If HACS says the repository is updated but the new services/entities are missing:

1. Use HACS **Redownload** for the integration.
2. Restart Home Assistant.
3. Check **Settings → System → Logs** for `maxspect_syna_g_local` errors.
4. Verify the integration is loaded under **Settings → Devices & services**.

If a controller is unavailable:

- Confirm Home Assistant can reach the controller host on TCP `12416`.
- Confirm the controller has a stable IP/hostname.
- Confirm the official app or original setup can still see the device.

## Development verification

```bash
python3 -m compileall -q custom_components scripts tests
python3 -m pytest -q
python3 scripts/probe_maxspect.py <device-ip-or-hostname>
```

Before publishing, also scan the repository for private hostnames, private IPs, and credentials.

## Compatibility

- Home Assistant: `2024.6.0` or newer, as declared in `hacs.json`.
- Installation type: HACS custom repository or manual custom component copy.
- Network: local polling.

## License

MIT. See [LICENSE](LICENSE).
