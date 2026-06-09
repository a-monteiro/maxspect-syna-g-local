#!/usr/bin/env python3
"""Build candidate Maxspect/Syna-G control payloads without sending them."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "maxspect_syna_g_local"))
from gagent import build_control_payload, probe  # noqa: E402


def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.2.86"
    result = probe(host)
    decoded = result.decoded_data or {}
    resume_auto = build_control_payload(decoded, {"MODE": 1}, serial=4)
    manual_zero = build_control_payload(
        decoded,
        {"channel_1": 0, "channel_2": 0, "channel_3": 0, "channel_4": 0, "channel_5": 0, "channel_6": 0},
        serial=4,
    )
    out = {
        "host": host,
        "online": result.online,
        "mode": decoded.get("MODE"),
        "channels": [decoded.get(f"channel_{i}") for i in range(1, 7)],
        "control_shape": "SN(4) + 0x11 + full-attribute LSB bitmap(3) + compact values in schema order",
        "verified_live": {
            "resume_auto_mode_1": "000000041100000401 set mode to 1 on aquarium-light-2",
            "mode_plus_channels_note": "writing channels switches device to manual mode; resume auto with mode-only afterwards",
        },
        "payloads_do_not_send_blindly": {
            "resume_auto_mode_1": resume_auto.hex(),
            "manual_channels_zero": manual_zero.hex(),
        },
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
